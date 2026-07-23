from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from rogueskills.agents.case_runtime import (
    CaseRunStore,
    CaseRuntimeError,
    CaseSkillStore,
)
from rogueskills.contracts.case_runtime import CaseEvaluation
from rogueskills.domain.case_pack import CasePack
from rogueskills.domain.case_run import (
    apply_case_mutation,
    case_evaluation_comparison,
    mutation_is_strict_improvement,
)

from .errors import ApplicationError


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CaseRunService:
    def __init__(self, *, skills: CaseSkillStore, cases: CaseRunStore) -> None:
        self.skills = skills
        self.cases = cases

    async def run(
        self,
        *,
        pack: CasePack,
        skill: dict[str, Any],
        case_input: dict[str, Any],
        mode: str,
        replay_case_id: str | None,
        auto_evolve: bool,
        run_id_prefix: str,
        initial_state_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated_input = (
            pack.input_model.model_validate(case_input).model_dump(mode="json")
            if pack.input_model is not None
            else dict(case_input)
        )
        case_id = f"{run_id_prefix}-{uuid4().hex}"
        state: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "id": case_id,
            "casePackId": pack.id,
            "casePackVersion": pack.version,
            "input": validated_input,
            "mode": mode,
            "replayCaseId": replay_case_id,
            "skillId": skill["id"],
            "baseSkillVersionId": skill["currentVersionId"],
            "evolvedSkillVersionId": None,
            "status": "running",
            "phase": "acquiring_sources",
            "runtimeVerified": False,
            "baseline": None,
            "mutation": None,
            "evolved": None,
            "comparison": None,
            "finalReport": None,
            "finalEvaluation": None,
            "runtimeArtifact": None,
            "createdAt": _iso_now(),
            "completedAt": None,
            "error": None,
            **(initial_state_fields or {}),
        }
        self.cases.save(state)
        try:
            bundle = await self._source_bundle(
                pack=pack,
                case_input=validated_input,
                mode=mode,
                replay_case_id=replay_case_id,
            )
            self.cases.save(state, source_bundle=bundle)
            state["phase"] = "building_dataset"
            self.cases.save(state)
            dataset = pack.dataset_builder.build(bundle, validated_input)

            state["phase"] = "executing_baseline"
            self.cases.save(state)
            baseline_report = await pack.runtime.execute(
                skill["genome"],
                self._runtime_context(
                    case_id=case_id,
                    stage="baseline",
                    skill_id=skill["id"],
                    skill_version_id=skill["currentVersionId"],
                    case_input=validated_input,
                ),
                dataset,
            )
            baseline_report = self._validate_report(pack, baseline_report)
            baseline_evaluation = pack.evaluator.evaluate(
                baseline_report,
                dataset,
                pack.runtime_policy,
            )
            state["baseline"] = {
                "report": baseline_report,
                "evaluation": baseline_evaluation.model_dump(mode="json"),
            }
            state["phase"] = "evaluating_baseline"
            self.cases.save(state)

            final_report = baseline_report
            final_evaluation = baseline_evaluation
            if (
                auto_evolve
                and not baseline_evaluation.passed
                and pack.mutation_planner is not None
                and pack.runtime_policy.maxMutationAttempts > 0
            ):
                final_report, final_evaluation = await self._run_mutation_attempt(
                    pack=pack,
                    state=state,
                    skill=skill,
                    case_input=validated_input,
                    mode=mode,
                    baseline_report=baseline_report,
                    baseline_evaluation=baseline_evaluation,
                    dataset=dataset,
                )

            state["status"] = "succeeded"
            state["phase"] = "completed"
            state["runtimeVerified"] = bool(
                final_evaluation.passed and final_evaluation.hardGatesPassed
            )
            state["finalReport"] = final_report
            state["finalEvaluation"] = final_evaluation.model_dump(mode="json")
            if state["runtimeVerified"] and pack.artifact_builder is not None:
                state["phase"] = "building_artifact"
                self.cases.save(state)
                artifact_fields = pack.artifact_builder.build(state, final_evaluation)
                state.update(artifact_fields)
                state["phase"] = "completed"
            state["completedAt"] = _iso_now()
            return self.cases.save(state)
        except CaseRuntimeError as error:
            application_error = ApplicationError(
                error.code,
                error.message,
                status_code=503,
                retryable=error.retryable,
                details={"caseId": case_id},
            )
            self._fail(state, application_error)
            raise application_error from error
        except ApplicationError as error:
            self._fail(state, error)
            error.details.setdefault("caseId", case_id)
            raise

    async def _source_bundle(
        self,
        *,
        pack: CasePack,
        case_input: dict[str, Any],
        mode: str,
        replay_case_id: str | None,
    ) -> dict[str, Any]:
        if mode == "verified_replay":
            if not replay_case_id:
                raise ApplicationError(
                    "REPLAY_CASE_ID_REQUIRED",
                    "verified_replay 模式需要 replayCaseId。",
                    status_code=422,
                )
            source = self.cases.get(replay_case_id, include_bundle=True)
            bundle = source.get("_sourceBundle") if source else None
            if not isinstance(bundle, dict) or not bundle:
                raise ApplicationError(
                    "VERIFIED_REPLAY_NOT_FOUND",
                    "找不到可重放的真实来源快照。",
                    status_code=404,
                )
            validator = getattr(pack.data_gateway, "validate_replay", None)
            if callable(validator):
                validator(bundle, case_input)
            return bundle
        if mode != "live":
            raise ApplicationError(
                "CASE_RUN_MODE_INVALID",
                f"不支持的 Case Run mode：{mode}",
                status_code=422,
            )
        return await pack.data_gateway.fetch_live(case_input, pack.runtime_policy.sourcePolicy)

    @staticmethod
    def _runtime_context(
        *,
        case_id: str,
        stage: str,
        skill_id: str,
        skill_version_id: str,
        case_input: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            **case_input,
            "caseId": case_id,
            "stage": stage,
            "skillId": skill_id,
            "skillVersionId": skill_version_id,
        }

    async def _run_mutation_attempt(
        self,
        *,
        pack: CasePack,
        state: dict[str, Any],
        skill: dict[str, Any],
        case_input: dict[str, Any],
        mode: str,
        baseline_report: dict[str, Any],
        baseline_evaluation: CaseEvaluation,
        dataset: dict[str, Any],
    ) -> tuple[dict[str, Any], CaseEvaluation]:
        assert pack.mutation_planner is not None
        proposal = pack.mutation_planner.propose(skill["genome"], baseline_evaluation)
        candidate_genome = apply_case_mutation(skill["genome"], proposal)
        state["mutation"] = {**proposal.model_dump(mode="json"), "status": "testing"}
        state["phase"] = "executing_evolved"
        self.cases.save(state)
        feedback = [item for item in baseline_evaluation.cases if not item.get("passed")]
        evolved_dataset = dataset
        source_failures = set(pack.runtime_policy.refreshOnFailedCaseIds) & set(
            baseline_evaluation.failedCaseIds
        )
        if mode == "live" and source_failures:
            refreshed_bundle = await pack.data_gateway.fetch_live(
                case_input,
                pack.runtime_policy.sourcePolicy,
            )
            evolved_dataset = pack.dataset_builder.build(refreshed_bundle, case_input)
            state["mutation"]["sourceRefresh"] = True
            self.cases.save(state, source_bundle=refreshed_bundle)
        evolved_report = await pack.runtime.execute(
            candidate_genome,
            self._runtime_context(
                case_id=state["id"],
                stage="evolved",
                skill_id=skill["id"],
                skill_version_id=f"{skill['currentVersionId']}+candidate",
                case_input=case_input,
            ),
            evolved_dataset,
            feedback=feedback,
        )
        evolved_report = self._validate_report(pack, evolved_report)
        evolved_evaluation = pack.evaluator.evaluate(
            evolved_report,
            evolved_dataset,
            pack.runtime_policy,
        )
        accepted = mutation_is_strict_improvement(baseline_evaluation, evolved_evaluation)
        if accepted:
            saved = self.skills.save_evolved_skill(
                candidate_genome,
                expected_version_id=skill["currentVersionId"],
                runtime_evidence={
                    "runtimeVerified": True,
                    "casePackId": pack.id,
                    "casePackVersion": pack.version,
                    "benchmarkId": evolved_evaluation.benchmarkId,
                    "evaluationId": evolved_evaluation.evaluationId,
                    "caseId": state["id"],
                    "input": case_input,
                    "score": evolved_evaluation.score,
                    "verifiedAt": _iso_now(),
                },
            )
            evolved_report["skillVersionId"] = saved["currentVersionId"]
            state["evolvedSkillVersionId"] = saved["currentVersionId"]
            state["mutation"]["status"] = "accepted"
            final_report = evolved_report
            final_evaluation = evolved_evaluation
        else:
            state["mutation"]["status"] = "rejected"
            final_report = baseline_report
            final_evaluation = baseline_evaluation
        state["evolved"] = {
            "report": evolved_report,
            "evaluation": evolved_evaluation.model_dump(mode="json"),
            "accepted": accepted,
        }
        state["comparison"] = case_evaluation_comparison(
            baseline_evaluation,
            evolved_evaluation,
            accepted=accepted,
        )
        return final_report, final_evaluation

    @staticmethod
    def _validate_report(pack: CasePack, report: dict[str, Any]) -> dict[str, Any]:
        if pack.report_model is None:
            return report
        try:
            return pack.report_model.model_validate(report).model_dump(mode="json")
        except ValidationError as error:
            raise ApplicationError(
                "CASE_REPORT_INVALID",
                "Case Runtime 输出不符合 Case Pack Report Contract。",
                status_code=502,
                details={"errors": error.errors(include_url=False)},
            ) from error

    def _fail(self, state: dict[str, Any], error: ApplicationError) -> None:
        state["status"] = "failed"
        state["phase"] = "failed"
        state["completedAt"] = _iso_now()
        state["error"] = {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        }
        self.cases.save(state)
