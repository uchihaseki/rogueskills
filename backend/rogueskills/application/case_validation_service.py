from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from rogueskills.adapters.agent_preset_loader import (
    AgentPresetIntegrityError,
    load_agent_preset,
)
from rogueskills.agents.case_runtime import CaseRunStore, CaseRuntimeError
from rogueskills.contracts.case_validation import (
    CaseValidationOption,
    CaseValidationState,
)
from rogueskills.domain.case_pack import CasePack
from rogueskills.domain.case_validation import (
    canonical_digest,
    case_validation_comparison,
    contribution_coverage,
    validation_idempotency_key,
)
from rogueskills.infrastructure.case_validation_repository import CaseValidationRepository
from rogueskills.infrastructure.preset_repository import AgentPresetRepository
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CaseValidationService:
    def __init__(
        self,
        *,
        skills: SkillRepository,
        presets: AgentPresetRepository,
        cases: CaseRunStore,
        validations: CaseValidationRepository,
    ) -> None:
        self.skills = skills
        self.presets = presets
        self.cases = cases
        self.validations = validations

    def create(
        self,
        *,
        run_id: str,
        pack: CasePack,
        replay_case_id: str,
        case_input: dict[str, Any],
        retry_failed: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        if pack.preset_runtime is None or "agent_preset_validation" not in pack.capabilities:
            raise ApplicationError(
                "CASE_PACK_PRESET_VALIDATION_UNSUPPORTED",
                "该 Case Pack 尚不支持 AgentPreset Validation。",
                status_code=409,
            )
        run_record = self.skills.get_run(run_id)
        if not run_record:
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        run = run_record["run"]
        if run.get("status") != "victory" or run.get("phase") != "ended":
            raise ApplicationError(
                "RUN_NOT_VICTORIOUS",
                "只有通过 Hidden Holdout 并生成 Candidate AgentPreset 的 Evaluation Run 才能执行 Runtime Validation。",
                status_code=409,
            )
        preset = self.presets.get_by_run_id(run_id)
        if not preset:
            raise ApplicationError(
                "AGENT_PRESET_NOT_AVAILABLE",
                "该 Evolution Run 尚未生成 AgentPreset。",
                status_code=409,
            )
        self._validate_lineage(run_record=run_record, preset=preset)
        validated_input = pack.validate_input(case_input)
        replay = self.cases.get(replay_case_id, include_bundle=True)
        if not replay or not isinstance(replay.get("_sourceBundle"), dict):
            raise ApplicationError(
                "VERIFIED_REPLAY_NOT_FOUND",
                "找不到具有真实持久化来源的 Verified Replay。",
                status_code=404,
            )
        demo_included = bool(replay.get("demoIncluded", False))
        replay_pack_id = str(replay.get("casePackId") or "finance-stock-analysis")
        replay_pack_version = str(replay.get("casePackVersion") or "1.0.0")
        if replay_pack_id != pack.id or replay_pack_version != pack.version:
            raise ApplicationError(
                "REPLAY_CASE_PACK_MISMATCH",
                "Replay Case 与请求的 Case Pack 不匹配。",
                status_code=409,
            )
        validator = getattr(pack.data_gateway, "validate_replay", None)
        if callable(validator):
            validator(replay["_sourceBundle"], validated_input)
        source_bundle_digest = canonical_digest(replay["_sourceBundle"])
        execution_policy = self._execution_policy(
            pack=pack, preset=preset, demo_included=demo_included
        )
        execution_policy_digest = canonical_digest(execution_policy)

        base_key = validation_idempotency_key(
            source_run_id=run_id,
            preset_digest=str(preset["digest"]),
            case_pack_ref=pack.ref,
            replay_case_id=replay_case_id,
            case_input=validated_input,
            source_bundle_digest=source_bundle_digest,
            execution_policy_digest=execution_policy_digest,
        )
        key = base_key
        retry_of_validation_id: str | None = None
        retry_count = 0
        existing = self.validations.get_by_idempotency_key(base_key)
        if retry_failed and (existing is None or existing.get("status") == "failed"):
            # A failed attempt created by an older execution policy may have a
            # different idempotency digest. Keep that evidence linked when the
            # presenter retries the same run/preset/replay selection. Prefer the
            # newest failed attempt so repeated retries form a direct chain.
            latest_failed = next(
                (
                    item
                    for item in self.validations.list_by_run(run_id, limit=100)
                    if item.get("status") == "failed"
                    and item.get("candidatePresetDigest") == str(preset["digest"])
                    and item.get("replayCaseId") == replay_case_id
                    and item.get("sourceBundleDigest") == source_bundle_digest
                    and item.get("input") == validated_input
                ),
                None,
            )
            if latest_failed is not None:
                existing = latest_failed
        if existing and existing.get("status") == "failed" and retry_failed:
            retry_of_validation_id = str(existing["id"])
            retry_count = max(1, int(existing.get("retryCount") or 0) + 1)
            while self.validations.get_by_idempotency_key(
                validation_idempotency_key(
                    source_run_id=run_id,
                    preset_digest=str(preset["digest"]),
                    case_pack_ref=pack.ref,
                    replay_case_id=replay_case_id,
                    case_input=validated_input,
                    source_bundle_digest=source_bundle_digest,
                    execution_policy_digest=execution_policy_digest,
                    retry_attempt=retry_count,
                )
            ):
                retry_count += 1
            key = validation_idempotency_key(
                source_run_id=run_id,
                preset_digest=str(preset["digest"]),
                case_pack_ref=pack.ref,
                replay_case_id=replay_case_id,
                case_input=validated_input,
                source_bundle_digest=source_bundle_digest,
                execution_policy_digest=execution_policy_digest,
                retry_attempt=retry_count,
            )
        elif existing:
            return existing, False
        state = CaseValidationState(
            id=f"case-validation-{uuid4().hex}",
            idempotencyKey=key,
            sourceRunId=run_id,
            candidatePresetId=str(preset["id"]),
            candidatePresetDigest=str(preset["digest"]),
            casePackId=pack.id,
            casePackVersion=pack.version,
            replayCaseId=replay_case_id,
            demoIncluded=demo_included,
            input=validated_input,
            skillId=str(run["baseSkillId"]),
            baseSkillVersionId=str(run_record["baseSkillVersionId"]),
            status="queued",
            phase="queued",
            sourceBundleDigest=source_bundle_digest,
            executionPolicy=execution_policy,
            executionPolicyDigest=execution_policy_digest,
            createdAt=_iso_now(),
            retryOfValidationId=retry_of_validation_id,
            retryCount=retry_count,
        ).model_dump(mode="json")
        return self.validations.save(state), True

    async def execute(self, validation_id: str, *, pack: CasePack) -> dict[str, Any]:
        state = self.get(validation_id)
        if state["status"] == "succeeded":
            return state
        if state["status"] == "failed":
            raise ApplicationError(
                "CASE_VALIDATION_ALREADY_FAILED",
                "该 CaseValidation 已失败，请创建新的验证。",
                status_code=409,
                details={"validationId": validation_id},
            )
        try:
            state["status"] = "running"
            state["phase"] = "loading_replay"
            self._save(state)
            replay = self.cases.get(state["replayCaseId"], include_bundle=True)
            bundle = replay.get("_sourceBundle") if replay else None
            if not isinstance(bundle, dict) or not bundle:
                raise ApplicationError(
                    "VERIFIED_REPLAY_NOT_FOUND",
                    "找不到具有真实持久化来源的 Verified Replay。",
                    status_code=404,
                )
            validator = getattr(pack.data_gateway, "validate_replay", None)
            if callable(validator):
                validator(bundle, state["input"])
            source_bundle_digest = canonical_digest(bundle)
            if (
                state.get("sourceBundleDigest")
                and state["sourceBundleDigest"] != source_bundle_digest
            ):
                raise ApplicationError(
                    "REPLAY_SOURCE_BUNDLE_CHANGED",
                    "Verified Replay 的来源快照与创建验证时锁定的 digest 不一致。",
                    status_code=409,
                )
            state["sourceBundleDigest"] = source_bundle_digest

            state["phase"] = "validating_preset"
            self._save(state)
            preset = self.presets.get(state["candidatePresetId"])
            if not preset or preset.get("digest") != state["candidatePresetDigest"]:
                raise ApplicationError(
                    "AGENT_PRESET_INTEGRITY_FAILED",
                    "CaseValidation 引用的 AgentPreset 已丢失或 digest 不匹配。",
                    status_code=409,
                )
            try:
                load_agent_preset(preset)
            except AgentPresetIntegrityError as error:
                raise ApplicationError(
                    "AGENT_PRESET_INTEGRITY_FAILED",
                    "AgentPreset 内容校验失败。",
                    status_code=409,
                ) from error
            run_record = self.skills.get_run(state["sourceRunId"])
            if not run_record:
                raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
            self._validate_lineage(run_record=run_record, preset=preset)
            version = self.skills.get_skill_version(state["baseSkillVersionId"])
            skill = self.skills.get_skill(state["skillId"])
            if not version or not skill or version["skillId"] != skill["id"]:
                raise ApplicationError(
                    "BASE_SKILL_VERSION_NOT_FOUND",
                    "Validation 固定的 Base Skill Version 不存在。",
                    status_code=409,
                )
            pinned_skill = {
                **skill,
                "currentVersionId": version["id"],
                "genome": version["genome"],
            }
            try:
                pack.validate_skill(pinned_skill)
            except ValueError as error:
                raise ApplicationError(
                    "CASE_PACK_SKILL_INCOMPATIBLE",
                    "Base Skill Version 不满足 Case Pack 准入策略。",
                    status_code=409,
                ) from error

            state["phase"] = "building_dataset"
            self._save(state)
            dataset = pack.dataset_builder.build(bundle, state["input"])
            dataset_digest = canonical_digest(dataset)
            if state.get("datasetDigest") and state["datasetDigest"] != dataset_digest:
                raise ApplicationError(
                    "CASE_VALIDATION_DATASET_CHANGED",
                    "同一验证重新构建的数据集 digest 不一致。",
                    status_code=409,
                )
            state["datasetDigest"] = dataset_digest
            current_execution_policy = self._execution_policy(
                pack=pack, preset=preset, demo_included=bool(state.get("demoIncluded"))
            )
            current_policy_digest = canonical_digest(current_execution_policy)
            if (
                state.get("executionPolicyDigest")
                and state["executionPolicyDigest"] != current_policy_digest
            ):
                raise ApplicationError(
                    "CASE_VALIDATION_EXECUTION_POLICY_CHANGED",
                    "Analyst、模型或执行预算与创建验证时锁定的策略不一致。",
                    status_code=409,
                )
            execution_policy = state.get("executionPolicy") or current_execution_policy
            state["executionPolicy"] = execution_policy
            state["executionPolicyDigest"] = current_policy_digest

            state["phase"] = "executing_baseline"
            self._save(state)
            baseline_report = await pack.runtime.execute(
                version["genome"],
                self._runtime_context(
                    state=state, stage="baseline", execution_policy=execution_policy
                ),
                dataset,
                feedback=None,
            )
            baseline_report = self._validate_report(pack, baseline_report)
            baseline_evaluation = pack.evaluator.evaluate(
                baseline_report, dataset, pack.runtime_policy
            )
            state["baseline"] = {
                "report": baseline_report,
                "evaluation": baseline_evaluation.model_dump(mode="json"),
            }
            state["phase"] = "evaluating_baseline"
            self._save(state)

            assert pack.preset_runtime is not None
            state["phase"] = "executing_candidate"
            self._save(state)
            candidate_report = await pack.preset_runtime.execute_preset(
                preset,
                self._runtime_context(
                    state=state, stage="candidate", execution_policy=execution_policy
                ),
                dataset,
                execution_policy,
            )
            candidate_report = self._validate_report(pack, candidate_report)
            candidate_evaluation = pack.evaluator.evaluate(
                candidate_report, dataset, pack.runtime_policy
            )
            state["candidate"] = {
                "report": candidate_report,
                "evaluation": candidate_evaluation.model_dump(mode="json"),
            }
            state["phase"] = "evaluating_candidate"
            self._save(state)

            state["phase"] = "comparing"
            comparison = case_validation_comparison(baseline_evaluation, candidate_evaluation)
            state["comparison"] = comparison
            state["runtimeVerified"] = bool(comparison["runtimeVerified"])
            state["accepted"] = bool(comparison["accepted"])
            state["contributionCoverage"] = contribution_coverage(
                preset=preset, comparison=comparison
            )
            state["promotion"] = {
                "status": "pending" if state["accepted"] else "not_eligible",
                "promoted": False,
                "evolvedSkillVersionId": None,
                "currentSkillVersionId": skill["currentVersionId"],
                "error": None,
            }
            if state["accepted"]:
                state["phase"] = "promoting"
                self._save(state)
                existing_promotion = self._existing_promotion(state)
                if existing_promotion is not None:
                    state["promotion"] = existing_promotion
                else:
                    try:
                        promoted = self.skills.save_verified_preset_binding(
                            skill_id=state["skillId"],
                            expected_version_id=state["baseSkillVersionId"],
                            preset_id=state["candidatePresetId"],
                            preset_digest=state["candidatePresetDigest"],
                            validation_id=state["id"],
                            runtime_evidence={
                                "runtimeVerified": True,
                                "mode": state["mode"],
                                "casePackId": state["casePackId"],
                                "casePackVersion": state["casePackVersion"],
                                "caseId": state["replayCaseId"],
                                "validationId": state["id"],
                                "presetId": state["candidatePresetId"],
                                "presetDigest": state["candidatePresetDigest"],
                                "evaluationId": candidate_evaluation.evaluationId,
                                "sourceDigest": state["sourceBundleDigest"],
                                "datasetDigest": state["datasetDigest"],
                                "executionPolicyDigest": state["executionPolicyDigest"],
                                "verifiedAt": _iso_now(),
                                "score": candidate_evaluation.score,
                            },
                        )
                        state["promotion"] = {
                            "status": "created",
                            "promoted": True,
                            "evolvedSkillVersionId": promoted["currentVersionId"],
                            "currentSkillVersionId": promoted["currentVersionId"],
                            "error": None,
                        }
                    except ApplicationError as error:
                        if error.code == "STALE_SKILL_VERSION":
                            state["promotion"] = {
                                "status": "version_conflict",
                                "promoted": False,
                                "evolvedSkillVersionId": None,
                                "currentSkillVersionId": error.details.get("currentVersionId"),
                                "error": {
                                    "code": error.code,
                                    "message": error.message,
                                },
                            }
                        else:
                            state["promotion"] = {
                                "status": "failed",
                                "promoted": False,
                                "evolvedSkillVersionId": None,
                                "currentSkillVersionId": skill["currentVersionId"],
                                "error": {
                                    "code": error.code,
                                    "message": error.message,
                                },
                            }
            state["status"] = "succeeded"
            state["phase"] = "completed"
            state["completedAt"] = _iso_now()
            return self._save(state)
        except CaseRuntimeError as error:
            application_error = ApplicationError(
                error.code,
                error.message,
                status_code=503,
                retryable=error.retryable,
                details={"validationId": validation_id},
            )
            self._fail(state, application_error)
            raise application_error from error
        except ApplicationError as error:
            self._fail(state, error)
            error.details.setdefault("validationId", validation_id)
            raise
        except Exception as error:
            application_error = ApplicationError(
                "CASE_VALIDATION_EXECUTION_FAILED",
                "CaseValidation 执行过程中发生未预期错误，已保留部分证据。",
                status_code=500,
                details={"validationId": validation_id, "errorType": type(error).__name__},
            )
            self._fail(state, application_error)
            raise application_error from error

    def get(self, validation_id: str) -> dict[str, Any]:
        state = self.validations.get(validation_id)
        if not state:
            raise ApplicationError(
                "CASE_VALIDATION_NOT_FOUND", "CaseValidation 不存在。", status_code=404
            )
        return state

    def list_for_run(self, run_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.skills.get_run(run_id):
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        return self.validations.list_by_run(run_id, limit=limit)

    def options(self, *, run_id: str, pack: CasePack, limit: int = 30) -> list[dict[str, Any]]:
        record = self.skills.get_run(run_id)
        if not record:
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        version = self.skills.get_skill_version(record["baseSkillVersionId"])
        skill = self.skills.get_skill(record["run"]["baseSkillId"])
        if not version or not skill:
            raise ApplicationError(
                "BASE_SKILL_VERSION_NOT_FOUND",
                "Run 固定的 Base Skill Version 不存在。",
                status_code=409,
            )
        pack.validate_skill(
            {**skill, "currentVersionId": version["id"], "genome": version["genome"]}
        )
        result: list[dict[str, Any]] = []
        for item in self.cases.list(limit=limit, case_pack_id=pack.id):  # type: ignore[attr-defined]
            if item.get("status") != "succeeded":
                continue
            if str(item.get("casePackVersion") or pack.version) != pack.version:
                continue
            complete = self.cases.get(str(item["id"]), include_bundle=True)
            bundle = complete.get("_sourceBundle") if complete else None
            if not isinstance(bundle, dict) or not bundle:
                continue
            sources = bundle.get("sources") if isinstance(bundle.get("sources"), list) else []
            source_providers = list(
                dict.fromkeys(
                    str(source.get("provider"))
                    for source in sources
                    if isinstance(source, dict) and source.get("provider")
                )
            )
            fetched = sorted(
                str(source.get("fetchedAt"))
                for source in sources
                if isinstance(source, dict) and source.get("fetchedAt")
            )
            case_input = item.get("input") or {
                "ticker": item.get("ticker"),
                "asOfDate": item.get("asOfDate"),
            }
            try:
                pack.validate_input(case_input)
                validator = getattr(pack.data_gateway, "validate_replay", None)
                if callable(validator):
                    validator(bundle, case_input)
            except (ApplicationError, ValidationError, ValueError):
                continue
            option = CaseValidationOption(
                caseId=str(item["id"]),
                casePackId=str(item.get("casePackId") or pack.id),
                casePackVersion=str(item.get("casePackVersion") or pack.version),
                mode="verified_replay",
                sourceMode=item.get("mode", "live"),
                input=case_input,
                caseLabel=item.get("caseLabel")
                or str((bundle.get("company") or {}).get("name") or "真实数据案例"),
                caseDescription=item.get("caseDescription"),
                ticker=case_input.get("ticker"),
                asOfDate=str(case_input.get("asOfDate")) if case_input.get("asOfDate") else None,
                sourceCount=len(sources),
                sourceProviders=source_providers,
                sourceCapturedAt=fetched[-1] if fetched else None,
                sourceBundleDigest=canonical_digest(bundle),
                demoIncluded=bool(item.get("demoIncluded", False)),
                sourceCaseId=item.get("sourceCaseId"),
                runtimeVerified=bool(item.get("runtimeVerified", False)),
                createdAt=item.get("createdAt"),
            )
            result.append(option.model_dump(mode="json"))
        return result

    @staticmethod
    def _validate_lineage(*, run_record: dict[str, Any], preset: dict[str, Any]) -> None:
        try:
            load_agent_preset(preset)
        except AgentPresetIntegrityError as error:
            raise ApplicationError(
                "AGENT_PRESET_INTEGRITY_FAILED",
                "AgentPreset 内容校验失败。",
                status_code=409,
            ) from error
        run = run_record["run"]
        source = preset.get("sourceRun") or {}
        primary = preset.get("primarySkill") or {}
        expected_version_id = run_record["baseSkillVersionId"]
        if (
            source.get("runId") != run["id"]
            or source.get("baseSkillId") != run["baseSkillId"]
            or source.get("baseSkillVersionId") != expected_version_id
            or primary.get("skillId") != run["baseSkillId"]
            or primary.get("skillVersionId") != expected_version_id
        ):
            raise ApplicationError(
                "AGENT_PRESET_LINEAGE_MISMATCH",
                "AgentPreset、Evolution Run 和 Base Skill Version lineage 不一致。",
                status_code=409,
            )

    @staticmethod
    def _execution_policy(
        *, pack: CasePack, preset: dict[str, Any], demo_included: bool = False
    ) -> dict[str, Any]:
        defaults = preset.get("runtimeDefaults") or {}
        timeout_ms = min(
            int(pack.runtime_policy.timeoutMs),
            int(defaults.get("timeoutMs") or pack.runtime_policy.timeoutMs),
        )
        analyst = getattr(pack.preset_runtime, "analyst", None)
        info = getattr(analyst, "info", None)
        if demo_included:
            demo_analyst = getattr(pack.preset_runtime, "demo_analyst", None)
            demo_info = getattr(demo_analyst, "info", None)
            if demo_info is not None:
                info = demo_info
        return {
            "contractVersion": "case-validation-execution-v1",
            "timeoutMs": timeout_ms,
            "maxTokens": int(defaults.get("maxTokens") or 12000),
            "maxToolCalls": int(defaults.get("maxToolCalls") or 0),
            "priority": str(defaults.get("priority") or "quality"),
            "enforceBudget": bool(defaults.get("enforceBudget", True)),
            "temperature": 0,
            "analyst": {
                "mode": getattr(info, "mode", "unknown"),
                "provider": getattr(info, "provider", "unknown"),
                "model": getattr(info, "model", None),
                "configured": bool(getattr(info, "configured", False)),
            },
            "toolAuthority": "case-pack",
        }

    @staticmethod
    def _runtime_context(
        *, state: dict[str, Any], stage: str, execution_policy: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            **state["input"],
            "caseId": state["id"],
            "stage": stage,
            "skillId": state["skillId"],
            "skillVersionId": state["baseSkillVersionId"],
            "candidatePresetId": state["candidatePresetId"] if stage == "candidate" else None,
            "executionKind": "agent_preset" if stage == "candidate" else "skill_version",
            "executionPolicy": execution_policy,
            "demoIncluded": bool(state.get("demoIncluded")),
        }

    def _existing_promotion(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Recover an already-created binding after a worker stops before final persistence."""

        current = self.skills.get_skill(state["skillId"])
        if not current or current.get("currentVersionId") == state["baseSkillVersionId"]:
            return None
        version = self.skills.get_skill_version(str(current.get("currentVersionId") or ""))
        binding = version.get("genome", {}).get("runtimeBinding") if version else None
        if not isinstance(binding, dict):
            return None
        if (
            binding.get("validationId") != state["id"]
            or binding.get("presetId") != state["candidatePresetId"]
            or binding.get("presetDigest") != state["candidatePresetDigest"]
        ):
            return None
        return {
            "status": "created",
            "promoted": True,
            "evolvedSkillVersionId": version["id"],
            "currentSkillVersionId": version["id"],
            "error": None,
        }

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

    def _save(self, state: dict[str, Any]) -> dict[str, Any]:
        validated = CaseValidationState.model_validate(state).model_dump(mode="json")
        saved = self.validations.save(validated)
        state.clear()
        state.update(saved)
        return saved

    def _fail(self, state: dict[str, Any], error: ApplicationError) -> None:
        state["status"] = "failed"
        state["phase"] = "failed"
        state["completedAt"] = _iso_now()
        state["error"] = {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
            "details": error.details,
        }
        self._save(state)
