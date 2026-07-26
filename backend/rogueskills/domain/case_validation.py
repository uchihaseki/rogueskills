from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from rogueskills.contracts.case_runtime import CaseEvaluation

FINANCE_CONTRIBUTION_TARGETS: dict[str, list[str]] = {
    "source_triangulation": ["source-integrity", "claim-citations"],
    "filing_recency_guard": ["source-integrity", "period-unit"],
    "accounting_normalizer": ["required-financials", "period-unit"],
    "earnings_quality_check": ["required-financials", "arithmetic-reconciliation"],
    "valuation_sensitivity": ["valuation-sensitivity"],
    "risk_register": ["advice-boundary"],
    "evidence_grade_analyst": ["claim-citations", "arithmetic-reconciliation"],
    "scenario_valuation_engine": ["valuation-sensitivity"],
    "risk_governed_research": ["advice-boundary"],
}


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def validation_idempotency_key(
    *,
    source_run_id: str,
    preset_digest: str,
    case_pack_ref: str,
    replay_case_id: str,
    case_input: Mapping[str, Any],
    source_bundle_digest: str,
    execution_policy_digest: str,
    retry_attempt: int = 0,
) -> str:
    payload = {
            "contractVersion": "case-validation-v1",
            "sourceRunId": source_run_id,
            "presetDigest": preset_digest,
            "casePackRef": case_pack_ref,
            "replayCaseId": replay_case_id,
            "input": dict(case_input),
            "sourceBundleDigest": source_bundle_digest,
            "executionPolicyDigest": execution_policy_digest,
        }
    if retry_attempt > 0:
        payload["retryAttempt"] = retry_attempt
    return canonical_digest(payload)


def case_validation_comparison(
    baseline: CaseEvaluation, candidate: CaseEvaluation
) -> dict[str, Any]:
    baseline_failed = set(baseline.failedCaseIds)
    candidate_failed = set(candidate.failedCaseIds)
    runtime_verified = bool(candidate.passed and candidate.hardGatesPassed)
    accepted = bool(runtime_verified and candidate.score > baseline.score)
    return {
        "baselineScore": baseline.score,
        "candidateScore": candidate.score,
        "scoreDelta": round(candidate.score - baseline.score, 1),
        "baselinePassed": baseline.passed,
        "candidatePassed": candidate.passed,
        "baselineHardGatesPassed": baseline.hardGatesPassed,
        "candidateHardGatesPassed": candidate.hardGatesPassed,
        "baselineFailedCaseIds": baseline.failedCaseIds,
        "candidateFailedCaseIds": candidate.failedCaseIds,
        "repairedCaseIds": sorted(baseline_failed - candidate_failed),
        "regressedCaseIds": sorted(candidate_failed - baseline_failed),
        "runtimeVerified": runtime_verified,
        "accepted": accepted,
    }


def contribution_coverage(
    *, preset: Mapping[str, Any], comparison: Mapping[str, Any]
) -> list[dict[str, Any]]:
    repaired = set(comparison.get("repairedCaseIds", []))
    result: list[dict[str, Any]] = []
    source_run = preset.get("sourceRun")
    if not isinstance(source_run, Mapping):
        return result
    for kind, key in (("mutation", "mutationIds"), ("evolution", "evolutionIds")):
        values = source_run.get(key, [])
        if not isinstance(values, list):
            continue
        for contribution_id in values:
            target_ids = FINANCE_CONTRIBUTION_TARGETS.get(str(contribution_id), [])
            result.append(
                {
                    "kind": kind,
                    "id": str(contribution_id),
                    "targetCaseIds": target_ids,
                    "repairedCaseIds": [item for item in target_ids if item in repaired],
                    "attribution": "associated_not_causal",
                }
            )
    return result
