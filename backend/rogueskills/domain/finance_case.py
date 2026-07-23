from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import jsonpatch  # type: ignore[import-untyped]

from rogueskills.contracts.finance_case import FinanceNarrative

from .shared import round_number

FLOW_TAGS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForProceedsFromOtherPropertyPlantAndEquipment",
    ],
    "diluted_eps": ["EarningsPerShareDiluted"],
}

POINT_TAGS: dict[str, list[tuple[str, str]]] = {
    "assets": [("us-gaap", "Assets")],
    "liabilities": [("us-gaap", "Liabilities")],
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    ],
    "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],
}

LABELS = {
    "revenue": "Revenue",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "operating_cash_flow": "Operating cash flow",
    "capex": "Capital expenditure",
    "diluted_eps": "Diluted EPS",
    "assets": "Total assets",
    "liabilities": "Total liabilities",
    "cash": "Cash and cash equivalents",
    "shares_outstanding": "Shares outstanding",
    "market_price": "Market close price",
}


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _duration_days(record: dict[str, Any]) -> int | None:
    try:
        return (date.fromisoformat(record["end"]) - date.fromisoformat(record["start"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _records(
    company_facts: dict[str, Any], namespace: str, tag: str
) -> list[dict[str, Any]]:
    fact = (company_facts.get("facts") or {}).get(namespace, {}).get(tag, {})
    result: list[dict[str, Any]] = []
    for unit, values in (fact.get("units") or {}).items():
        for value in values:
            if value.get("val") is None:
                continue
            result.append({**value, "unit": unit, "namespace": namespace, "tag": tag})
    return result


def _deduplicate_by_end(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for record in records:
        end = str(record.get("end") or "")
        current = chosen.get(end)
        if not current or str(record.get("filed") or "") > str(current.get("filed") or ""):
            chosen[end] = record
    return sorted(chosen.values(), key=lambda item: str(item.get("end") or ""), reverse=True)


def _annual_records(
    company_facts: dict[str, Any], tags: list[str], as_of_date: str
) -> list[dict[str, Any]]:
    for tag in tags:
        candidates = [
            record
            for record in _records(company_facts, "us-gaap", tag)
            if record.get("form") == "10-K"
            and record.get("fp") == "FY"
            and str(record.get("filed") or "") <= as_of_date
            and (days := _duration_days(record)) is not None
            and 300 <= days <= 400
        ]
        selected = _deduplicate_by_end(candidates)
        if selected:
            return selected[:2]
    return []


def _quarter_record(
    company_facts: dict[str, Any], tags: list[str], as_of_date: str
) -> dict[str, Any] | None:
    for tag in tags:
        candidates = [
            record
            for record in _records(company_facts, "us-gaap", tag)
            if record.get("form") == "10-Q"
            and str(record.get("filed") or "") <= as_of_date
            and (days := _duration_days(record)) is not None
            and 70 <= days <= 110
        ]
        selected = _deduplicate_by_end(candidates)
        if selected:
            return selected[0]
    return None


def _point_record(
    company_facts: dict[str, Any], candidates: list[tuple[str, str]], as_of_date: str
) -> dict[str, Any] | None:
    for namespace, tag in candidates:
        records = [
            record
            for record in _records(company_facts, namespace, tag)
            if record.get("form") in {"10-K", "10-Q"}
            and str(record.get("filed") or "") <= as_of_date
            and record.get("end")
        ]
        selected = _deduplicate_by_end(records)
        if selected:
            return selected[0]
    return None


def _fact(
    *,
    metric: str,
    suffix: str,
    record: dict[str, Any],
    cik: int,
) -> dict[str, Any]:
    accession = record.get("accn")
    source_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
        f"{str(accession).replace('-', '')}/"
        if accession
        else f"https://www.sec.gov/edgar/browse/?CIK={cik}"
    )
    return {
        "id": f"fact-{metric}-{suffix}",
        "metric": f"{metric}_{suffix}",
        "label": f"{LABELS[metric]} ({suffix.replace('_', ' ')})",
        "value": float(record["val"]),
        "unit": str(record["unit"]),
        "periodStart": record.get("start"),
        "periodEnd": str(record["end"]),
        "form": str(record.get("form") or "SEC"),
        "filed": str(record.get("filed") or ""),
        "accession": accession,
        "factName": f"{record['namespace']}:{record['tag']}",
        "sourceEvidenceId": "sec-companyfacts",
        "sourceUrl": source_url,
    }


def _derived(
    metric_id: str,
    label: str,
    value: float,
    unit: str,
    formula: str,
    inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": f"metric-{metric_id}",
        "label": label,
        "value": float(round_number(value, 4)),
        "unit": unit,
        "formula": formula,
        "inputFactIds": [item["id"] for item in inputs],
        "evidenceIds": list(
            dict.fromkeys([item["sourceEvidenceId"] for item in inputs])
        ),
    }


def build_finance_dataset(bundle: dict[str, Any]) -> dict[str, Any]:
    company = bundle["company"]
    facts_payload = bundle["companyFacts"]
    as_of_date = bundle["asOfDate"]
    cik = int(company["cik"])
    facts: list[dict[str, Any]] = []
    annual_by_metric: dict[str, list[dict[str, Any]]] = {}

    for metric, tags in FLOW_TAGS.items():
        records = _annual_records(facts_payload, tags, as_of_date)
        annual_facts = [
            _fact(
                metric=metric,
                suffix="annual_current" if index == 0 else "annual_previous",
                record=record,
                cik=cik,
            )
            for index, record in enumerate(records)
        ]
        annual_by_metric[metric] = annual_facts
        facts.extend(annual_facts)
        quarter = _quarter_record(facts_payload, tags, as_of_date)
        if quarter:
            facts.append(_fact(metric=metric, suffix="quarter_latest", record=quarter, cik=cik))

    for metric, point_tags in POINT_TAGS.items():
        record = _point_record(facts_payload, point_tags, as_of_date)
        if record:
            facts.append(_fact(metric=metric, suffix="latest", record=record, cik=cik))

    market = bundle.get("market")
    if market:
        facts.append(
            {
                "id": "fact-market-price-latest",
                "metric": "market_price_latest",
                "label": LABELS["market_price"],
                "value": float(market["close"]),
                "unit": market["currency"],
                "periodStart": market["date"],
                "periodEnd": market["date"],
                "form": "MARKET",
                "filed": market["date"],
                "accession": None,
                "factName": "Stooq:Close",
                "sourceEvidenceId": market["sourceEvidenceId"],
                "sourceUrl": next(
                    source["url"]
                    for source in bundle["sources"]
                    if source["id"] == market["sourceEvidenceId"]
                ),
            }
        )

    by_metric = {item["metric"]: item for item in facts}
    derived: list[dict[str, Any]] = []
    revenue = annual_by_metric.get("revenue", [])
    if len(revenue) >= 2 and revenue[1]["value"]:
        derived.append(
            _derived(
                "revenue-growth",
                "Annual revenue growth",
                (revenue[0]["value"] / revenue[1]["value"] - 1) * 100,
                "%",
                "(current annual revenue / previous annual revenue - 1) × 100",
                revenue[:2],
            )
        )
    if revenue:
        for metric, label in [
            ("gross_profit", "Gross margin"),
            ("operating_income", "Operating margin"),
            ("net_income", "Net margin"),
        ]:
            values = annual_by_metric.get(metric, [])
            if values and revenue[0]["value"]:
                derived.append(
                    _derived(
                        metric.replace("_", "-") + "-margin",
                        label,
                        values[0]["value"] / revenue[0]["value"] * 100,
                        "%",
                        f"current annual {metric} / current annual revenue × 100",
                        [values[0], revenue[0]],
                    )
                )
    ocf = annual_by_metric.get("operating_cash_flow", [])
    capex = annual_by_metric.get("capex", [])
    if ocf and capex:
        derived.append(
            _derived(
                "free-cash-flow",
                "Free cash flow",
                ocf[0]["value"] - abs(capex[0]["value"]),
                ocf[0]["unit"],
                "current annual operating cash flow - absolute current annual capex",
                [ocf[0], capex[0]],
            )
        )

    eps = by_metric.get("diluted_eps_annual_current")
    shares = by_metric.get("shares_outstanding_latest")
    fcf = next((item for item in derived if item["id"] == "metric-free-cash-flow"), None)
    scenarios: list[dict[str, Any]] = []
    for name, pe, fcf_yield in [
        ("bear", 20.0, 0.05),
        ("base", 25.0, 0.04),
        ("bull", 30.0, 0.03),
    ]:
        scenarios.append(
            {
                "name": name,
                "peMultiple": pe,
                "impliedPriceByPe": (
                    float(round_number(eps["value"] * pe, 2)) if eps else None
                ),
                "fcfYield": fcf_yield,
                "impliedPriceByFcf": (
                    float(round_number(fcf["value"] / shares["value"] / fcf_yield, 2))
                    if fcf and shares and shares["value"]
                    else None
                ),
            }
        )

    submissions = bundle["submissions"]
    recent = (submissions.get("filings") or {}).get("recent") or {}
    filings = []
    count = len(recent.get("accessionNumber") or [])
    for index in range(count):
        filed = str((recent.get("filingDate") or [""] * count)[index])
        form = str((recent.get("form") or [""] * count)[index])
        if filed <= as_of_date and form in {"10-K", "10-Q"}:
            accession = str(recent["accessionNumber"][index])
            filings.append(
                {
                    "form": form,
                    "filed": filed,
                    "reportDate": str((recent.get("reportDate") or [""] * count)[index]),
                    "accession": accession,
                    "primaryDocument": str(
                        (recent.get("primaryDocument") or [""] * count)[index]
                    ),
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                        f"{accession.replace('-', '')}/"
                    ),
                }
            )
        if len(filings) >= 4:
            break

    return {
        "company": company,
        "asOfDate": as_of_date,
        "sources": bundle["sources"],
        "filings": filings,
        "facts": facts,
        "derivedMetrics": derived,
        "valuationScenarios": scenarios,
        "warnings": bundle.get("warnings", []),
        "validEvidenceIds": [
            *[item["id"] for item in bundle["sources"]],
            *[item["id"] for item in facts],
            *[item["id"] for item in derived],
        ],
    }


def build_finance_report(
    *,
    case_id: str,
    stage: str,
    skill_id: str,
    skill_version_id: str,
    dataset: dict[str, Any],
    narrative: FinanceNarrative,
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "id": f"report-{uuid4().hex}",
        "caseId": case_id,
        "stage": stage,
        "generatedAt": _iso_now(),
        "skillId": skill_id,
        "skillVersionId": skill_version_id,
        "company": dataset["company"],
        "asOfDate": dataset["asOfDate"],
        "sources": dataset["sources"],
        "filings": dataset["filings"],
        "facts": dataset["facts"],
        "derivedMetrics": dataset["derivedMetrics"],
        "valuationScenarios": dataset["valuationScenarios"],
        "warnings": dataset.get("warnings", []),
        "narrative": narrative.model_dump(mode="json"),
    }


def _case(
    case_id: str,
    label: str,
    score: float,
    weight: int,
    details: str,
    *,
    passed: bool | None = None,
    hard_gate: bool = False,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    normalized = float(round_number(score, 1))
    return {
        "id": case_id,
        "label": label,
        "score": normalized,
        "weight": weight,
        "passed": normalized >= 80 if passed is None else passed,
        "hardGate": hard_gate,
        "details": details,
        "evidenceRefs": evidence_refs or [],
    }


def evaluate_finance_report(report: dict[str, Any]) -> dict[str, Any]:
    sources = report["sources"]
    facts = report["facts"]
    metrics = report["derivedMetrics"]
    narrative = report["narrative"]
    valid_ids = {
        *[item["id"] for item in sources],
        *[item["id"] for item in facts],
        *[item["id"] for item in metrics],
    }
    specific_ids = {item["id"] for item in facts} | {item["id"] for item in metrics}
    source_integrity = all(
        item.get("url", "").startswith("https://")
        and str(item.get("sha256", "")).startswith("sha256:")
        for item in sources
    ) and {"sec-submissions", "sec-companyfacts"}.issubset(
        {item["id"] for item in sources}
    )
    provider_count = len({item["provider"] for item in sources})
    source_passed = source_integrity and provider_count >= 2
    source_score = 100 if source_passed else 65 if source_integrity else 0

    required_metrics = {
        "revenue_annual_current",
        "net_income_annual_current",
        "operating_cash_flow_annual_current",
        "capex_annual_current",
    }
    available_metrics = {item["metric"] for item in facts}
    required_coverage = len(required_metrics & available_metrics) / len(required_metrics)
    has_fcf = any(item["id"] == "metric-free-cash-flow" for item in metrics)
    financial_score = required_coverage * 85 + (15 if has_fcf else 0)

    findings = narrative.get("findings", [])
    refs = [ref for item in findings for ref in item.get("evidenceIds", [])]
    valid_ref_ratio = sum(ref in valid_ids for ref in refs) / len(refs) if refs else 0
    specifically_evidenced = sum(
        any(ref in specific_ids for ref in item.get("evidenceIds", [])) for item in findings
    )
    specific_ratio = specifically_evidenced / len(findings) if findings else 0
    citation_score = (valid_ref_ratio * 0.4 + specific_ratio * 0.6) * 100
    citations_passed = citation_score >= 80

    period_complete = sum(
        bool(item.get("periodEnd") and item.get("unit") and item.get("filed")) for item in facts
    ) / len(facts) if facts else 0
    period_score = period_complete * 100

    fcf_metric = next(
        (item for item in metrics if item["id"] == "metric-free-cash-flow"), None
    )
    fact_by_id = {item["id"]: item for item in facts}
    arithmetic_ok = False
    if fcf_metric and len(fcf_metric["inputFactIds"]) == 2:
        first, second = [fact_by_id.get(item) for item in fcf_metric["inputFactIds"]]
        if first and second:
            expected = first["value"] - abs(second["value"])
            arithmetic_ok = abs(expected - fcf_metric["value"]) <= max(1, abs(expected) * 1e-8)
    arithmetic_score = 100 if arithmetic_ok else 45 if not fcf_metric else 0

    scenarios = report["valuationScenarios"]
    valuation_complete = (
        len(scenarios) == 3
        and all(item.get("impliedPriceByPe") is not None for item in scenarios)
        and all(item.get("impliedPriceByFcf") is not None for item in scenarios)
    )
    valuation_score = 100 if valuation_complete else 50 if len(scenarios) == 3 else 0

    text = " ".join(
        [narrative.get("summary", ""), narrative.get("conclusionBoundary", "")]
        + [item.get("claim", "") for item in findings]
    ).lower()
    unsafe_patterns = [
        r"\byou should (?:buy|sell)\b",
        r"\brecommend(?:s|ed|ing)? (?:buying|selling)\b",
        r"\b(?:buy|sell) (?:this|the) stock\b",
        r"\b(?:guarantees?|will deliver) (?:a )?returns?\b",
        r"(?<!不)保证收益",
        r"必涨",
        r"建议(?:买入|卖出)",
        r"应该(?:买入|卖出)",
    ]
    safe = not any(re.search(pattern, text, flags=re.I) for pattern in unsafe_patterns)
    safety_score = 100 if safe else 0

    cases = [
        _case(
            "source-integrity",
            "Immutable source integrity",
            source_score,
            15,
            f"{len(sources)} snapshots across {provider_count} provider(s)",
            passed=source_passed,
            hard_gate=True,
            evidence_refs=[item["id"] for item in sources],
        ),
        _case(
            "required-financials",
            "Required financial coverage",
            financial_score,
            20,
            f"{len(required_metrics & available_metrics)}/{len(required_metrics)} core facts; FCF={has_fcf}",
            passed=required_coverage == 1 and has_fcf,
        ),
        _case(
            "claim-citations",
            "Fact-level claim citations",
            citation_score,
            20,
            f"valid refs {valid_ref_ratio:.0%}; fact-level findings {specific_ratio:.0%}",
            passed=citations_passed,
            hard_gate=True,
        ),
        _case(
            "period-unit",
            "Period and unit completeness",
            period_score,
            15,
            f"complete fact metadata {period_complete:.0%}",
            passed=period_complete == 1,
        ),
        _case(
            "arithmetic-reconciliation",
            "Derived metric reconciliation",
            arithmetic_score,
            10,
            "FCF reconciles to operating cash flow less absolute capex"
            if arithmetic_ok
            else "FCF cannot be reconciled",
            passed=arithmetic_ok,
        ),
        _case(
            "valuation-sensitivity",
            "Two-method valuation sensitivity",
            valuation_score,
            15,
            "bear/base/bull PE and FCF-yield scenarios"
            if valuation_complete
            else "one or more valuation methods are unavailable",
            passed=valuation_complete,
        ),
        _case(
            "advice-boundary",
            "Investment advice boundary",
            safety_score,
            5,
            "No personalized advice or guaranteed-return language" if safe else "unsafe advice language",
            passed=safe,
            hard_gate=True,
        ),
    ]
    score = sum(item["score"] * item["weight"] for item in cases) / sum(
        item["weight"] for item in cases
    )
    hard_gates_passed = all(item["passed"] for item in cases if item["hardGate"])
    passed = score >= 85 and hard_gates_passed
    failed = [item for item in cases if not item["passed"]]
    return {
        "evaluationId": f"finance-eval-{uuid4().hex}",
        "benchmarkId": "finance-real-case-v1",
        "algorithmVersion": "finance-evidence-evaluator-v1",
        "runtimeVerified": passed,
        "passed": passed,
        "score": float(round_number(score, 1)),
        "hardGatesPassed": hard_gates_passed,
        "cases": cases,
        "failedCaseIds": [item["id"] for item in failed],
        "summary": "真实金融 Case 通过证据验收" if passed else "真实金融 Case 仍有证据或输出缺口",
    }


def plan_finance_mutation(
    genome: dict[str, Any], evaluation: dict[str, Any]
) -> dict[str, Any]:
    failed = set(evaluation.get("failedCaseIds", []))
    patch: list[dict[str, Any]] = []
    tools = set(genome.get("tools", []))
    for tool in ["SEC EDGAR", "MarketData"]:
        if tool not in tools:
            patch.append({"op": "add", "path": "/tools/-", "value": tool})
    steps = genome.get("workflow", {}).get("steps", [])
    next_order = max((int(item.get("order", 0)) for item in steps), default=0) + 1
    instructions = [
        (
            "Capture SEC filing, XBRL fact, and as-of market-price snapshots with URL, "
            "period, unit, access date, and SHA-256 before analysis."
        ),
        (
            "Attach fact or derived-metric evidence IDs to every time-sensitive claim and "
            "reconcile free cash flow to its source facts."
        ),
        (
            "Produce bear, base, and bull valuation sensitivity using both diluted-EPS "
            "multiples and free-cash-flow yield."
        ),
    ]
    for offset, instruction in enumerate(instructions):
        if not any(item.get("instruction") == instruction for item in steps):
            patch.append(
                {
                    "op": "add",
                    "path": "/workflow/steps/-",
                    "value": {
                        "id": f"runtime-evidence-{next_order + offset}",
                        "order": next_order + offset,
                        "instruction": instruction,
                    },
                }
            )
    constraints = set(genome.get("constraints", []))
    new_constraints = [
        "Every factual claim must cite a fact or derived-metric evidence ID from the current run.",
        "Reject period, currency, unit, and filing-date mismatches instead of silently inferring values.",
        "Do not issue personalized investment advice, a buy/sell command, or a guaranteed-return claim.",
    ]
    for constraint in new_constraints:
        if constraint not in constraints:
            patch.append({"op": "add", "path": "/constraints/-", "value": constraint})
    tags = set(genome.get("metadata", {}).get("tags", []))
    for tag in ["source-triangulation", "accounting-normalizer", "valuation-sensitivity"]:
        if tag not in tags:
            patch.append({"op": "add", "path": "/metadata/tags/-", "value": tag})
    return {
        "id": f"finance-mutation-{uuid4().hex}",
        "name": "Evidence-bound Finance Runtime",
        "reason": "; ".join(sorted(failed)) or "No failed evaluator cases",
        "evidenceRefs": [item["id"] for item in evaluation.get("cases", []) if not item["passed"]],
        "tradeoff": "Adds source and validation steps, increasing latency and tool calls.",
        "genomePatch": patch,
        "tags": ["source-triangulation", "accounting-normalizer", "valuation-sensitivity"],
        "algorithmVersion": "finance-mutation-planner-v1",
    }


def apply_finance_mutation(
    genome: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    evolved: dict[str, Any] = jsonpatch.JsonPatch(proposal["genomePatch"]).apply(
        deepcopy(genome)
    )
    evolved["status"] = "initial"
    evolved["runtimeEvolution"] = {
        "proposalId": proposal["id"],
        "algorithmVersion": proposal["algorithmVersion"],
        "appliedAt": _iso_now(),
    }
    return evolved
