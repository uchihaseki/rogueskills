from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import jsonpatch  # type: ignore[import-untyped]

from rogueskills.contracts.case_runtime import CaseEvaluation, CaseMutationProposal


def apply_case_mutation(
    genome: dict[str, Any], proposal: CaseMutationProposal
) -> dict[str, Any]:
    evolved: dict[str, Any] = jsonpatch.JsonPatch(proposal.genomePatch).apply(deepcopy(genome))
    evolved["status"] = "initial"
    evolved["runtimeEvolution"] = {
        "proposalId": proposal.id,
        "algorithmVersion": proposal.algorithmVersion,
        "appliedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    return evolved


def mutation_is_strict_improvement(
    baseline: CaseEvaluation, evolved: CaseEvaluation
) -> bool:
    return bool(evolved.passed and evolved.hardGatesPassed and evolved.score > baseline.score)


def case_evaluation_comparison(
    baseline: CaseEvaluation, evolved: CaseEvaluation, *, accepted: bool
) -> dict[str, Any]:
    return {
        "baselineScore": baseline.score,
        "evolvedScore": evolved.score,
        "scoreDelta": round(evolved.score - baseline.score, 1),
        "accepted": accepted,
        "baselineFailedCaseIds": baseline.failedCaseIds,
        "evolvedFailedCaseIds": evolved.failedCaseIds,
    }
