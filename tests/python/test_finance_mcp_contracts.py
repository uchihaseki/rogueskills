from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from rogueskills.contracts.finance_mcp import (
    FINANCE_MCP_REDACTED_FIELDS,
    FinanceMcpAnalyzeStockInput,
    FinanceMcpEvaluation,
    FinanceMcpLimits,
    FinanceMcpReportEnvelope,
    build_finance_mcp_report,
    finance_mcp_error_from_api,
    summarize_finance_case,
)


def _evaluation(*, passed: bool = True, score: float = 100.0) -> dict[str, object]:
    return {
        "evaluationId": "finance-eval-test",
        "benchmarkId": "finance-real-case-v1",
        "algorithmVersion": "finance-evidence-evaluator-v1",
        "runtimeVerified": passed,
        "passed": passed,
        "score": score,
        "hardGatesPassed": passed,
        "cases": [
            {
                "id": "source-integrity",
                "label": "Immutable source integrity",
                "score": score,
                "weight": 15,
                "passed": passed,
                "hardGate": True,
                "details": "source snapshots",
                "evidenceRefs": ["sec-companyfacts"],
            }
        ],
        "failedCaseIds": [] if passed else ["source-integrity"],
        "summary": "passed" if passed else "failed",
    }


def _report(stage: str = "final") -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "id": f"report-{stage}",
        "caseId": "finance-case-test",
        "stage": stage,
        "generatedAt": "2026-07-23T00:00:00Z",
        "skillId": "sop-test",
        "skillVersionId": "sop-test@2",
        "sources": [
            {
                "id": "sec-companyfacts",
                "provider": "SEC EDGAR",
                "title": "Company facts",
                "url": "https://data.sec.gov/companyfacts.json",
                "fetchedAt": "2026-07-23T00:00:00Z",
                "sha256": "sha256:" + "a" * 64,
                "contentType": "application/json",
            }
        ],
        "facts": [{"id": "fact-1"}],
        "warnings": [
            {
                "code": "MARKET_PRICE_NOT_AVAILABLE",
                "message": "Fallback provider was used.",
                "retryable": True,
            }
        ],
    }


def _case() -> dict[str, object]:
    evaluation = _evaluation()
    final_report = _report()
    return {
        "id": "finance-case-test",
        "ticker": "aapl",
        "asOfDate": "2026-07-21",
        "mode": "live",
        "skillId": "sop-test",
        "baseSkillVersionId": "sop-test@2",
        "evolvedSkillVersionId": None,
        "status": "succeeded",
        "phase": "completed",
        "runtimeVerified": True,
        "baseline": {"report": final_report, "evaluation": evaluation},
        "evolved": None,
        "comparison": None,
        "finalReport": final_report,
        "finalEvaluation": evaluation,
        "agentPreset": {
            "id": "preset-test",
            "digest": "sha256:" + "b" * 64,
            "status": "candidate",
            "primarySkill": {"skillVersionId": "sop-test@2"},
            "evaluationEvidence": {"runtimeVerified": True},
        },
        "error": None,
    }


def test_analyze_input_normalizes_ticker_and_keeps_safe_evolution_default() -> None:
    request = FinanceMcpAnalyzeStockInput(
        ticker=" aapl ", asOfDate=date(2026, 7, 21), skillId=" sop-test "
    )

    assert request.ticker == "AAPL"
    assert request.skillId == "sop-test"
    assert request.mode == "live"
    assert request.autoEvolve is False


def test_analyze_input_requires_replay_case_for_verified_replay() -> None:
    with pytest.raises(ValidationError, match="replayCaseId is required"):
        FinanceMcpAnalyzeStockInput(
            ticker="AAPL",
            asOfDate=date(2026, 7, 21),
            skillId="sop-test",
            mode="verified_replay",
        )

    with pytest.raises(ValidationError, match="only valid"):
        FinanceMcpAnalyzeStockInput(
            ticker="AAPL",
            asOfDate=date(2026, 7, 21),
            skillId="sop-test",
            replayCaseId="finance-case-test",
        )


def test_summarize_success_case_preserves_verification_and_counts() -> None:
    summary = summarize_finance_case(_case())

    assert summary.caseId == "finance-case-test"
    assert summary.ticker == "AAPL"
    assert summary.asOfDate == date(2026, 7, 21)
    assert summary.runtimeVerified is True
    assert summary.finalScore == 100
    assert summary.sourceCount == 1
    assert summary.factCount == 1
    assert summary.warningCount == 1
    assert summary.agentPreset is not None
    assert summary.agentPreset.runtimeVerified is True


def test_summary_requires_case_and_final_evaluation_to_agree_on_verification() -> None:
    case = _case()
    case["finalEvaluation"] = _evaluation(passed=False, score=94.8)

    summary = summarize_finance_case(case)

    assert case["runtimeVerified"] is True
    assert summary.runtimeVerified is False
    assert summary.evaluation is not None
    assert summary.evaluation.hardGatesPassed is False


def test_summarize_rejected_mutation_keeps_failure_evidence() -> None:
    case = _case()
    failed_evaluation = _evaluation(passed=False, score=89.8)
    case["runtimeVerified"] = False
    case["finalEvaluation"] = failed_evaluation
    case["agentPreset"] = None
    case["mutation"] = {
        "id": "mutation-test",
        "status": "rejected",
        "reason": "source-integrity; advice-boundary",
        "tradeoff": "Adds latency.",
        "sourceRefresh": True,
    }
    case["comparison"] = {
        "baselineScore": 94.8,
        "evolvedScore": 89.8,
        "scoreDelta": -5.0,
        "accepted": False,
        "baselineFailedCaseIds": ["source-integrity"],
        "evolvedFailedCaseIds": ["source-integrity", "advice-boundary"],
    }

    summary = summarize_finance_case(case)

    assert summary.runtimeVerified is False
    assert summary.agentPreset is None
    assert summary.mutation is not None
    assert summary.mutation.status == "rejected"
    assert summary.mutation.sourceRefresh is True
    assert summary.comparison is not None
    assert summary.comparison.accepted is False
    assert summary.comparison.evolvedFailedCaseIds == [
        "source-integrity",
        "advice-boundary",
    ]


def test_summarize_failed_case_keeps_error_without_report() -> None:
    case = _case()
    case.update(
        {
            "status": "failed",
            "phase": "failed",
            "runtimeVerified": False,
            "baseline": None,
            "finalReport": None,
            "finalEvaluation": None,
            "agentPreset": None,
            "error": {
                "code": "FINANCE_ANALYST_NOT_CONFIGURED",
                "message": "Analyst is unavailable.",
                "retryable": False,
            },
        }
    )

    summary = summarize_finance_case(case)

    assert summary.status == "failed"
    assert summary.finalScore is None
    assert summary.sourceCount == 0
    assert summary.error is not None
    assert summary.error.code == "FINANCE_ANALYST_NOT_CONFIGURED"


def test_report_envelope_is_stage_aware_and_keeps_fallback_warning() -> None:
    envelope = build_finance_mcp_report(_case(), "final")

    assert isinstance(envelope, FinanceMcpReportEnvelope)
    assert envelope.caseId == "finance-case-test"
    assert envelope.stage == "final"
    assert envelope.skillVersionId == "sop-test@2"
    assert envelope.sources[0].sha256.startswith("sha256:")
    assert envelope.warnings[0].code == "MARKET_PRICE_NOT_AVAILABLE"
    assert envelope.evaluation is not None
    assert envelope.evaluation.runtimeVerified is True
    assert envelope.window.totalFactCount == 1
    assert envelope.window.truncated is False


def test_report_envelope_pages_facts_without_mutating_persisted_report() -> None:
    case = _case()
    report = case["finalReport"]
    assert isinstance(report, dict)
    report["facts"] = [{"id": f"fact-{index}"} for index in range(5)]

    envelope = build_finance_mcp_report(case, "final", fact_offset=1, fact_limit=2)

    assert [item["id"] for item in envelope.report["facts"]] == ["fact-1", "fact-2"]
    assert envelope.window.totalFactCount == 5
    assert envelope.window.returnedFactCount == 2
    assert envelope.window.factOffset == 1
    assert envelope.window.hasMoreFacts is True
    assert envelope.window.truncated is True
    assert len(report["facts"]) == 5


def test_report_envelope_rejects_missing_stage() -> None:
    case = _case()
    case["baseline"] = None

    with pytest.raises(ValueError, match="baseline"):
        build_finance_mcp_report(case, "baseline")


def test_api_error_is_normalized_with_case_and_request_ids() -> None:
    error = finance_mcp_error_from_api(
        {
            "error": {
                "code": "FINANCE_ANALYST_NOT_CONFIGURED",
                "message": "Analyst is unavailable.",
                "retryable": False,
                "details": {"caseId": "finance-case-test"},
            },
            "requestId": "req-test",
        },
        status_code=503,
    )

    assert error.code == "FINANCE_ANALYST_NOT_CONFIGURED"
    assert error.caseId == "finance-case-test"
    assert error.requestId == "req-test"
    assert error.details["statusCode"] == 503


def test_api_error_redacts_secret_like_detail_keys() -> None:
    error = finance_mcp_error_from_api(
        {
            "error": {
                "code": "UPSTREAM_ERROR",
                "message": "failed",
                "details": {
                    "Authorization": "Bearer secret",
                    "nested": {"apiKey": "secret-2"},
                    "safe": "kept",
                },
            }
        }
    )

    assert error.details == {
        "Authorization": "[REDACTED]",
        "nested": {"apiKey": "[REDACTED]"},
        "safe": "kept",
    }


def test_mcp_evaluation_contract_keeps_full_case_diagnostics() -> None:
    evaluation = FinanceMcpEvaluation.model_validate(_evaluation())

    assert evaluation.cases[0].hardGate is True
    assert evaluation.cases[0].evidenceRefs == ["sec-companyfacts"]


def test_bridge_limits_and_redaction_policy_are_frozen() -> None:
    limits = FinanceMcpLimits()

    assert limits.caseExecutionTimeoutMs == 420_000
    assert limits.maxInlineReportBytes == 256_000
    assert {"authorization", "x-api-key", "token"} <= FINANCE_MCP_REDACTED_FIELDS
