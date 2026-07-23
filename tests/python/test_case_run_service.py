from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from rogueskills.agents.case_runtime import CaseRuntimeError
from rogueskills.application.case_run_service import CaseRunService
from rogueskills.contracts.case_runtime import (
    CaseEvaluation,
    CaseMutationProposal,
    CaseRuntimePolicy,
    CaseSkillPolicy,
    CaseSourcePolicy,
)
from rogueskills.domain.case_pack import CasePack


class GenericInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


class GenericGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch_live(self, case_input: dict[str, Any], source_policy: Any) -> dict[str, Any]:
        del case_input, source_policy
        self.calls += 1
        return {"source": "live", "version": self.calls}


class GenericBuilder:
    def build(self, source_bundle: dict[str, Any], case_input: dict[str, Any]) -> dict[str, Any]:
        return {"source": source_bundle, "value": case_input["value"]}


class GenericRuntime:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        genome: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del dataset, feedback
        self.calls += 1
        return {
            "caseId": case_input["caseId"],
            "stage": case_input["stage"],
            "skillVersionId": case_input["skillVersionId"],
            "quality": genome["quality"],
        }


class GenericEvaluator:
    def evaluate(
        self,
        report: dict[str, Any],
        dataset: dict[str, Any],
        policy: CaseRuntimePolicy,
    ) -> CaseEvaluation:
        del dataset, policy
        passed = report["quality"] >= 80
        return CaseEvaluation(
            evaluationId=f"eval-{report['stage']}",
            benchmarkId="generic-case-v1",
            algorithmVersion="generic-evaluator-v1",
            runtimeVerified=passed,
            passed=passed,
            score=float(report["quality"]),
            hardGatesPassed=passed,
            cases=[
                {
                    "id": "quality",
                    "label": "Quality",
                    "score": float(report["quality"]),
                    "weight": 100,
                    "passed": passed,
                    "hardGate": True,
                    "details": "generic quality",
                    "evidenceRefs": [],
                }
            ],
            failedCaseIds=[] if passed else ["quality"],
            summary="generic result",
        )


class GenericPlanner:
    def propose(
        self, genome: dict[str, Any], evaluation: CaseEvaluation
    ) -> CaseMutationProposal:
        del evaluation
        return CaseMutationProposal(
            id="mutation-generic-quality",
            sourceSkillVersionId=str(genome["id"]),
            name="Improve generic quality",
            reason="quality",
            evidenceRefs=["quality"],
            tradeoff="Adds a validation step.",
            tags=["quality"],
            genomePatch=[{"op": "replace", "path": "/quality", "value": 90}],
            algorithmVersion="generic-planner-v1",
        )


class GenericArtifacts:
    def build(self, case_run: dict[str, Any], evaluation: CaseEvaluation) -> dict[str, Any]:
        return {
            "runtimeArtifact": {
                "id": "artifact-generic",
                "caseRunId": case_run["id"],
                "casePackId": case_run["casePackId"],
                "casePackVersion": case_run["casePackVersion"],
                "skillVersionId": case_run.get("evolvedSkillVersionId")
                or case_run["baseSkillVersionId"],
                "evaluationId": evaluation.evaluationId,
                "digest": "sha256:" + "a" * 64,
            }
        }


class GenericSkillStore:
    def __init__(self, skill: dict[str, Any]) -> None:
        self.skill = deepcopy(skill)
        self.saved = 0

    def save_evolved_skill(
        self,
        genome: dict[str, Any],
        *,
        expected_version_id: str,
        runtime_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert expected_version_id == self.skill["currentVersionId"]
        assert runtime_evidence is not None
        self.saved += 1
        self.skill["currentVersionId"] = "generic-skill@2"
        self.skill["genome"] = genome
        return {"currentVersionId": "generic-skill@2", "genome": genome}


class GenericCaseStore:
    def __init__(self) -> None:
        self.states: dict[str, dict[str, Any]] = {}
        self.bundles: dict[str, dict[str, Any]] = {}

    def save(
        self,
        state: dict[str, Any],
        *,
        source_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.states[state["id"]] = deepcopy(state)
        if source_bundle is not None:
            self.bundles[state["id"]] = deepcopy(source_bundle)
        return deepcopy(state)

    def get(self, case_id: str, *, include_bundle: bool = False) -> dict[str, Any] | None:
        state = deepcopy(self.states.get(case_id))
        if state is not None and include_bundle:
            state["_sourceBundle"] = deepcopy(self.bundles.get(case_id))
        return state


def generic_pack(gateway: GenericGateway, runtime: GenericRuntime) -> CasePack:
    return CasePack(
        id="generic-case",
        version="1.0.0",
        name="Generic Case",
        description="A non-finance test Case Pack.",
        input_model=GenericInput,
        report_model=None,
        capabilities=("live", "auto_evolve", "runtime_artifact"),
        skill_policy=CaseSkillPolicy(),
        runtime_policy=CaseRuntimePolicy(
            sourcePolicy=CaseSourcePolicy(maxSnapshots=2),
        ),
        data_gateway=gateway,
        dataset_builder=GenericBuilder(),
        runtime=runtime,
        evaluator=GenericEvaluator(),
        mutation_planner=GenericPlanner(),
        artifact_builder=GenericArtifacts(),
        state_projector=lambda case_input: {"value": case_input["value"]},
        preflight_provider=lambda: {"ready": True, "runtime": "generic-case@1.0.0"},
    )


@pytest.mark.asyncio
async def test_generic_case_run_service_does_not_depend_on_finance_behavior() -> None:
    gateway = GenericGateway()
    runtime = GenericRuntime()
    skill = {
        "id": "generic-skill",
        "currentVersionId": "generic-skill@1",
        "status": "initial",
        "genome": {"id": "generic-skill", "quality": 90},
    }
    store = GenericCaseStore()
    skill_store = GenericSkillStore(skill)
    service = CaseRunService(skills=skill_store, cases=store)

    result = await service.run(
        pack=generic_pack(gateway, runtime),
        skill=skill,
        case_input={"value": 7},
        mode="live",
        replay_case_id=None,
        auto_evolve=True,
        run_id_prefix="generic-case",
    )

    assert result["casePackId"] == "generic-case"
    assert result["status"] == "succeeded"
    assert result["runtimeVerified"] is True
    assert result["mutation"] is None
    assert result["runtimeArtifact"]["casePackId"] == "generic-case"
    assert gateway.calls == 1
    assert runtime.calls == 1
    assert skill_store.saved == 0


@pytest.mark.asyncio
async def test_generic_case_run_service_accepts_strictly_better_mutation() -> None:
    gateway = GenericGateway()
    runtime = GenericRuntime()
    skill = {
        "id": "generic-skill",
        "currentVersionId": "generic-skill@1",
        "status": "initial",
        "genome": {"id": "generic-skill", "quality": 40},
    }
    store = GenericCaseStore()
    skill_store = GenericSkillStore(skill)
    service = CaseRunService(skills=skill_store, cases=store)

    result = await service.run(
        pack=generic_pack(gateway, runtime),
        skill=skill,
        case_input={"value": 7},
        mode="live",
        replay_case_id=None,
        auto_evolve=True,
        run_id_prefix="generic-case",
    )

    assert result["runtimeVerified"] is True
    assert result["mutation"]["status"] == "accepted"
    assert result["evolvedSkillVersionId"] == "generic-skill@2"
    assert result["comparison"]["scoreDelta"] == 50.0
    assert result["finalReport"]["skillVersionId"] == "generic-skill@2"
    assert skill_store.saved == 1
    assert runtime.calls == 2


def test_case_runtime_error_is_a_stable_runtime_boundary() -> None:
    error = CaseRuntimeError("GENERIC_RUNTIME_FAILED", "runtime failed", retryable=True)

    assert error.code == "GENERIC_RUNTIME_FAILED"
    assert error.message == "runtime failed"
    assert error.retryable is True
