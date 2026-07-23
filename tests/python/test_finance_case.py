from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from rogueskills.adapters.finance_data import SecFinanceDataGateway
from rogueskills.agents.finance_analyst import FinanceAnalystInfo
from rogueskills.api.app import create_app
from rogueskills.contracts.finance_case import FinanceNarrative
from rogueskills.contracts.finance_mcp import build_finance_mcp_report, summarize_finance_case
from rogueskills.domain.finance_case import build_finance_dataset, evaluate_finance_report
from rogueskills.infrastructure.database import CaseRunRow, FinanceCaseRunRow
from rogueskills.settings import Settings

from .fakes import FinanceFixtureMaterialNormalizer


def _annual(
    value: float,
    *,
    unit: str,
    tag: str,
    start: str,
    end: str,
    filed: str,
    accession: str,
) -> dict[str, Any]:
    return {
        "start": start,
        "end": end,
        "val": value,
        "accn": accession,
        "fy": int(end[:4]),
        "fp": "FY",
        "form": "10-K",
        "filed": filed,
        "frame": None,
        "unit": unit,
        "namespace": "us-gaap",
        "tag": tag,
    }


def _fact_payload(tag: str, unit: str, current: float, previous: float) -> dict[str, Any]:
    del tag
    return {
        "units": {
            unit: [
                {
                    key: value
                    for key, value in _annual(
                        current,
                        unit=unit,
                        tag="unused",
                        start="2024-09-29",
                        end="2025-09-27",
                        filed="2025-10-31",
                        accession="0000320193-25-000079",
                    ).items()
                    if key not in {"unit", "namespace", "tag"}
                },
                {
                    key: value
                    for key, value in _annual(
                        previous,
                        unit=unit,
                        tag="unused",
                        start="2023-10-01",
                        end="2024-09-28",
                        filed="2024-11-01",
                        accession="0000320193-24-000123",
                    ).items()
                    if key not in {"unit", "namespace", "tag"}
                },
            ]
        }
    }


def finance_bundle() -> dict[str, Any]:
    current_accession = "0000320193-25-000079"
    filed = "2025-10-31"
    point = lambda value, unit="USD": {  # noqa: E731
        "end": "2025-09-27",
        "val": value,
        "accn": current_accession,
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "filed": filed,
    }
    return {
        "company": {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "cik": 320193,
            "sic": "3571",
            "sicDescription": "Electronic Computers",
            "fiscalYearEnd": "0927",
        },
        "asOfDate": "2026-07-22",
        "sources": [
            {
                "id": "sec-submissions",
                "provider": "SEC EDGAR",
                "title": "AAPL submissions",
                "url": "https://data.sec.gov/submissions/CIK0000320193.json",
                "fetchedAt": "2026-07-22T00:00:00Z",
                "sha256": "sha256:" + "a" * 64,
                "contentType": "application/json",
            },
            {
                "id": "sec-companyfacts",
                "provider": "SEC EDGAR",
                "title": "AAPL company facts",
                "url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
                "fetchedAt": "2026-07-22T00:00:00Z",
                "sha256": "sha256:" + "b" * 64,
                "contentType": "application/json",
            },
            {
                "id": "market-price",
                "provider": "Stooq",
                "title": "AAPL market price",
                "url": "https://stooq.com/q/d/l/?s=aapl.us",
                "fetchedAt": "2026-07-22T00:00:00Z",
                "sha256": "sha256:" + "c" * 64,
                "contentType": "text/csv",
            },
        ],
        "submissions": {
            "filings": {
                "recent": {
                    "accessionNumber": [current_accession],
                    "filingDate": [filed],
                    "reportDate": ["2025-09-27"],
                    "form": ["10-K"],
                    "primaryDocument": ["aapl-20250927.htm"],
                }
            }
        },
        "companyFacts": {
            "entityName": "Apple Inc.",
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": _fact_payload(
                        "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "USD",
                        420_000_000_000,
                        391_000_000_000,
                    ),
                    "GrossProfit": _fact_payload(
                        "GrossProfit", "USD", 195_000_000_000, 180_000_000_000
                    ),
                    "OperatingIncomeLoss": _fact_payload(
                        "OperatingIncomeLoss", "USD", 130_000_000_000, 123_000_000_000
                    ),
                    "NetIncomeLoss": _fact_payload(
                        "NetIncomeLoss", "USD", 105_000_000_000, 97_000_000_000
                    ),
                    "NetCashProvidedByUsedInOperatingActivities": _fact_payload(
                        "NetCashProvidedByUsedInOperatingActivities",
                        "USD",
                        125_000_000_000,
                        118_000_000_000,
                    ),
                    "PaymentsToAcquirePropertyPlantAndEquipment": _fact_payload(
                        "PaymentsToAcquirePropertyPlantAndEquipment",
                        "USD",
                        12_000_000_000,
                        11_000_000_000,
                    ),
                    "EarningsPerShareDiluted": _fact_payload(
                        "EarningsPerShareDiluted", "USD/shares", 7.2, 6.5
                    ),
                    "Assets": {"units": {"USD": [point(360_000_000_000)]}},
                    "Liabilities": {"units": {"USD": [point(290_000_000_000)]}},
                    "CashAndCashEquivalentsAtCarryingValue": {
                        "units": {"USD": [point(31_000_000_000)]}
                    },
                },
                "dei": {
                    "EntityCommonStockSharesOutstanding": {
                        "units": {"shares": [point(15_000_000_000, "shares")]}
                    }
                },
            },
        },
        "market": {
            "ticker": "AAPL",
            "date": "2026-07-21",
            "close": 215.0,
            "currency": "USD",
            "provider": "Stooq",
            "sourceEvidenceId": "market-price",
        },
        "warnings": [],
        "rawSnapshots": {
            "sec-submissions": "{}",
            "sec-companyfacts": "{}",
            "market-price": "Date,Close\n2026-07-21,215\n",
        },
    }


class FixtureFinanceDataGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_bundle(self, *, ticker: str, as_of_date: Any) -> dict[str, Any]:
        self.calls += 1
        assert ticker == "AAPL"
        assert as_of_date.isoformat() == "2026-07-22"
        return deepcopy(finance_bundle())


class ImprovingFinanceAnalyst:
    calls = 0

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="llm", provider="fixture", model="finance-fixture", configured=True
        )

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> FinanceNarrative:
        del case, dataset
        self.calls += 1
        evolved = bool(feedback)
        if evolved:
            assert "SEC EDGAR" in genome["tools"]
        evidence = (
            [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
            if evolved
            else ["sec-companyfacts"] * 3
        )
        return FinanceNarrative.model_validate(
            {
                "summary": "Evidence-bound public-company analysis.",
                "findings": [
                    {
                        "id": f"finding-{index}",
                        "kind": "fact",
                        "claim": f"Verified finding {index}.",
                        "evidenceIds": [evidence[index]],
                    }
                    for index in range(3)
                ],
                "risks": [
                    {"id": "risk-1", "risk": "Demand may weaken.", "evidenceIds": []},
                    {"id": "risk-2", "risk": "Margins may compress.", "evidenceIds": []},
                ],
                "dataGaps": [],
                "conclusionBoundary": "This is public-information research, not investment advice.",
            }
        )


class PassingFinanceAnalyst:
    def __init__(self, *, unsafe_when_evolved: bool = False) -> None:
        self.calls = 0
        self.unsafe_when_evolved = unsafe_when_evolved

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="llm", provider="fixture", model="finance-passing-fixture", configured=True
        )

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> FinanceNarrative:
        del genome, case, dataset
        self.calls += 1
        unsafe = bool(feedback) and self.unsafe_when_evolved
        return FinanceNarrative.model_validate(
            {
                "summary": "Evidence-bound public-company analysis.",
                "findings": [
                    {
                        "id": "finding-revenue",
                        "kind": "fact",
                        "claim": "Revenue is tied to the annual filing fact.",
                        "evidenceIds": ["fact-revenue-annual_current"],
                    },
                    {
                        "id": "finding-income",
                        "kind": "fact",
                        "claim": "Net income is tied to the annual filing fact.",
                        "evidenceIds": ["fact-net_income-annual_current"],
                    },
                    {
                        "id": "finding-fcf",
                        "kind": "inference",
                        "claim": "Free cash flow reconciles to source facts.",
                        "evidenceIds": ["metric-free-cash-flow"],
                    },
                ],
                "risks": [
                    {"id": "risk-1", "risk": "Demand may weaken.", "evidenceIds": []},
                    {"id": "risk-2", "risk": "Margins may compress.", "evidenceIds": []},
                ],
                "dataGaps": [],
                "conclusionBoundary": (
                    "You should buy this stock."
                    if unsafe
                    else "This is public-information research, not investment advice."
                ),
            }
        )


class SingleProviderFinanceDataGateway(FixtureFinanceDataGateway):
    async def fetch_bundle(self, *, ticker: str, as_of_date: Any) -> dict[str, Any]:
        bundle = await super().fetch_bundle(ticker=ticker, as_of_date=as_of_date)
        for source in bundle["sources"]:
            source["provider"] = "SEC EDGAR"
        return bundle


def _finance_skill(api: TestClient) -> dict[str, Any]:
    converted = api.post(
        "/api/materials/convert",
        json={
            "title": "Listed Company Finance SOP",
            "license": "internal",
            "kind": "finance-sop",
            "content": "Analyze filings, cash flow, valuation, and risks with evidence.",
        },
    ).json()["genome"]
    converted["metadata"]["category"] = "finance"
    stored = api.post(
        "/api/skills", json={"genome": converted, "sourceId": "test-finance"}
    ).json()["skill"]
    benchmark = api.post(f"/api/skills/{stored['id']}/benchmark", json={}).json()
    promoted = api.post(
        f"/api/skills/{stored['id']}/promote",
        json={
            "evaluationId": benchmark["evaluation"]["id"],
            "expectedSkillVersionId": stored["currentVersionId"],
        },
    )
    assert promoted.status_code == 200
    return promoted.json()["skill"]


def test_finance_dataset_and_evaluator_reconcile_real_metrics() -> None:
    dataset = build_finance_dataset(finance_bundle())
    assert dataset["company"]["ticker"] == "AAPL"
    assert {item["metric"] for item in dataset["facts"]} >= {
        "revenue_annual_current",
        "net_income_annual_current",
        "operating_cash_flow_annual_current",
        "capex_annual_current",
    }
    fcf = next(item for item in dataset["derivedMetrics"] if item["id"] == "metric-free-cash-flow")
    assert fcf["value"] == 113_000_000_000
    assert all(item["impliedPriceByPe"] for item in dataset["valuationScenarios"])
    assert all(item["impliedPriceByFcf"] for item in dataset["valuationScenarios"])


def test_real_finance_case_executes_evaluates_mutates_and_versions_skill(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'finance-case.db'}",
        project_root=Path(__file__).parents[2],
        llm_base_url=None,
        llm_model=None,
    )
    analyst = ImprovingFinanceAnalyst()
    gateway = FixtureFinanceDataGateway()
    app = create_app(
        settings,
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=gateway,  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)
        response = api.post(
            "/api/finance/cases",
            json={
                "ticker": "AAPL",
                "skillId": skill["id"],
                "asOfDate": "2026-07-22",
                "mode": "live",
                "autoEvolve": True,
            },
        )
        assert response.status_code == 201
        case = response.json()["case"]
        assert analyst.calls == 2
        assert case["status"] == "succeeded"
        assert case["runtimeVerified"] is True
        assert case["baseline"]["evaluation"]["passed"] is False
        assert case["evolved"]["evaluation"]["passed"] is True
        assert case["comparison"]["scoreDelta"] > 0
        assert case["mutation"]["status"] == "accepted"
        assert case["evolvedSkillVersionId"] != case["baseSkillVersionId"]
        assert case["finalReport"]["skillVersionId"] == case["evolvedSkillVersionId"]
        assert case["financeEvolutionRunId"] == f"run-real-{case['id']}"
        assert case["agentPreset"]["evaluationEvidence"]["mode"] == "real-finance-case-v1"
        assert case["agentPreset"]["evaluationEvidence"]["runtimeVerified"] is True
        with app.state.case_run_repository.sessions() as session:
            assert session.scalar(select(func.count()).select_from(CaseRunRow)) == 1
            assert session.scalar(select(func.count()).select_from(FinanceCaseRunRow)) == 0

        mcp_summary = summarize_finance_case(case)
        assert mcp_summary.caseId == case["id"]
        assert mcp_summary.runtimeVerified is True
        assert mcp_summary.finalScore == case["finalEvaluation"]["score"]
        assert mcp_summary.evolvedSkillVersionId == case["evolvedSkillVersionId"]
        assert mcp_summary.agentPreset is not None
        assert mcp_summary.agentPreset.digest == case["agentPreset"]["digest"]
        mcp_report = build_finance_mcp_report(case, "final")
        assert mcp_report.report["id"] == case["finalReport"]["id"]
        assert mcp_report.evaluation is not None
        assert mcp_report.evaluation.hardGatesPassed is True

        saved_skill = api.get(f"/api/skills/{skill['id']}").json()["skill"]
        assert saved_skill["currentVersionId"] == case["evolvedSkillVersionId"]
        assert saved_skill["genome"]["runtimeVerification"]["runtimeVerified"] is True
        assert len(saved_skill["versions"]) == 3

        loaded = api.get(f"/api/finance/cases/{case['id']}")
        assert loaded.status_code == 200
        assert loaded.json()["case"]["id"] == case["id"]
        report = api.get(f"/api/finance/cases/{case['id']}/report?stage=final")
        assert report.status_code == 200
        assert report.json()["report"]["id"] == case["finalReport"]["id"]
        preset = api.get(f"/api/finance/cases/{case['id']}/agent-preset")
        assert preset.status_code == 200
        assert preset.json()["preset"]["digest"] == case["agentPreset"]["digest"]
        runtime = api.get(
            f"/api/agent-presets/{case['agentPreset']['id']}/runtime-config"
        )
        assert runtime.status_code == 200
        assert runtime.json()["runtimeConfig"]["runtimeVerified"] is True
        exported = api.get(
            f"/api/agent-presets/{case['agentPreset']['id']}/export/universal"
        )
        assert exported.status_code == 200

        replay = api.post(
            "/api/finance/cases",
            json={
                "ticker": "AAPL",
                "skillId": skill["id"],
                "asOfDate": "2026-07-22",
                "mode": "verified_replay",
                "replayCaseId": case["id"],
                "autoEvolve": False,
            },
        )
        assert replay.status_code == 201
        assert replay.json()["case"]["mode"] == "verified_replay"
        assert gateway.calls == 1


def test_passing_baseline_does_not_create_redundant_skill_version(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'finance-baseline-pass.db'}",
        project_root=Path(__file__).parents[2],
        llm_base_url=None,
        llm_model=None,
    )
    analyst = PassingFinanceAnalyst()
    app = create_app(
        settings,
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)
        initial_version_count = len(skill["versions"])
        response = api.post(
            "/api/finance/cases",
            json={
                "ticker": "AAPL",
                "skillId": skill["id"],
                "asOfDate": "2026-07-22",
                "mode": "live",
                "autoEvolve": True,
            },
        )

        assert response.status_code == 201
        case = response.json()["case"]
        assert analyst.calls == 1
        assert case["runtimeVerified"] is True
        assert case["mutation"] is None
        assert case["evolved"] is None
        assert case["comparison"] is None
        assert case["evolvedSkillVersionId"] is None
        assert case["finalReport"]["id"] == case["baseline"]["report"]["id"]
        saved_skill = api.get(f"/api/skills/{skill['id']}").json()["skill"]
        assert len(saved_skill["versions"]) == initial_version_count


def test_regressing_mutation_is_rejected_and_preserves_baseline(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'finance-rejected-mutation.db'}",
        project_root=Path(__file__).parents[2],
        llm_base_url=None,
        llm_model=None,
    )
    analyst = PassingFinanceAnalyst(unsafe_when_evolved=True)
    gateway = SingleProviderFinanceDataGateway()
    app = create_app(
        settings,
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=gateway,  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)
        initial_version_count = len(skill["versions"])
        response = api.post(
            "/api/finance/cases",
            json={
                "ticker": "AAPL",
                "skillId": skill["id"],
                "asOfDate": "2026-07-22",
                "mode": "live",
                "autoEvolve": True,
            },
        )

        assert response.status_code == 201
        case = response.json()["case"]
        assert analyst.calls == 2
        assert gateway.calls == 2
        assert case["runtimeVerified"] is False
        assert case["mutation"]["status"] == "rejected"
        assert case["evolved"]["accepted"] is False
        assert case["comparison"]["accepted"] is False
        assert case["comparison"]["scoreDelta"] < 0
        assert case["evolvedSkillVersionId"] is None
        assert case["finalReport"]["id"] == case["baseline"]["report"]["id"]
        assert case["agentPreset"] is None
        saved_skill = api.get(f"/api/skills/{skill['id']}").json()["skill"]
        assert len(saved_skill["versions"]) == initial_version_count


def test_evaluator_rejects_generic_source_only_citations() -> None:
    dataset = build_finance_dataset(finance_bundle())
    report = {
        "sources": dataset["sources"],
        "facts": dataset["facts"],
        "derivedMetrics": dataset["derivedMetrics"],
        "valuationScenarios": dataset["valuationScenarios"],
        "narrative": {
            "summary": "Public-source analysis.",
            "conclusionBoundary": "Not investment advice.",
            "findings": [
                {
                    "id": f"f-{index}",
                    "kind": "fact",
                    "claim": "A claim.",
                    "evidenceIds": ["sec-companyfacts"],
                }
                for index in range(3)
            ],
        },
    }
    evaluation = evaluate_finance_report(report)
    assert evaluation["passed"] is False
    assert "claim-citations" in evaluation["failedCaseIds"]


@pytest.mark.asyncio
async def test_sec_gateway_captures_public_source_hashes_and_price() -> None:
    bundle = finance_bundle()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.sec.gov" and request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json={"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}})
        if request.url.host == "data.sec.gov" and request.url.path.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=bundle["submissions"])
        if request.url.host == "data.sec.gov" and "/companyfacts/" in request.url.path:
            return httpx.Response(200, json=bundle["companyFacts"])
        if request.url.host == "stooq.com":
            return httpx.Response(
                200,
                text="Date,Open,High,Low,Close,Volume\n2026-07-21,214,216,213,215,100\n",
                headers={"content-type": "text/csv"},
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetched = await SecFinanceDataGateway(
            client, sec_user_agent="RogueSkills test test@example.com"
        ).fetch_bundle(ticker="AAPL", as_of_date=date(2026, 7, 22))
    assert fetched["market"]["close"] == 215
    assert {item["id"] for item in fetched["sources"]} == {
        "sec-submissions",
        "sec-companyfacts",
        "market-price",
    }
    assert all(item["sha256"].startswith("sha256:") for item in fetched["sources"])


@pytest.mark.asyncio
async def test_sec_gateway_uses_yahoo_when_stooq_has_no_row() -> None:
    bundle = finance_bundle()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.sec.gov" and request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json={"0": {"ticker": "AAPL", "cik_str": 320193}})
        if request.url.host == "data.sec.gov" and request.url.path.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=bundle["submissions"])
        if request.url.host == "data.sec.gov" and "/companyfacts/" in request.url.path:
            return httpx.Response(200, json=bundle["companyFacts"])
        if request.url.host == "stooq.com":
            return httpx.Response(200, text="No data", headers={"content-type": "text/csv"})
        if request.url.host == "query1.finance.yahoo.com":
            return httpx.Response(
                200,
                json={
                    "chart": {
                        "result": [
                            {
                                "timestamp": [1784592000],
                                "indicators": {"quote": [{"close": [215.5]}]},
                                "meta": {"currency": "USD"},
                            }
                        ]
                    }
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetched = await SecFinanceDataGateway(
            client, sec_user_agent="RogueSkills test test@example.com"
        ).fetch_bundle(ticker="AAPL", as_of_date=date(2026, 7, 22))
    assert fetched["market"]["provider"] == "Yahoo Finance"
    assert fetched["market"]["close"] == 215.5
    assert fetched["warnings"][0]["code"] == "MARKET_PRICE_NOT_AVAILABLE"
    assert {item["provider"] for item in fetched["sources"]} == {
        "SEC EDGAR",
        "Yahoo Finance",
    }
