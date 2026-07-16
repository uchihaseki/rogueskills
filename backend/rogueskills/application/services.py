from copy import deepcopy
from typing import Any
from uuid import uuid4

from rogueskills.agents.material_normalizer import MaterialNormalizer, MaterialNormalizerError
from rogueskills.domain.benchmark import run_admission_benchmark
from rogueskills.domain.discovery import build_skill_genome_from_normalized
from rogueskills.domain.evolution import (
    choose_mutation,
    create_run,
    resolve_current_node,
    select_node,
    skip_mutation,
)
from rogueskills.domain.genome import validate_skill_genome
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class MaterialService:
    def __init__(self, normalizer: MaterialNormalizer) -> None:
        self.normalizer = normalizer

    async def convert(
        self,
        *,
        title: str | None,
        content: str,
        source: dict[str, Any] | None,
        license_value: str,
        kind: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            normalized = await self.normalizer.normalize(
                title=title,
                content=content,
                kind=kind,
            )
        except MaterialNormalizerError as error:
            status_code = (
                503
                if error.code == "LLM_NORMALIZER_NOT_CONFIGURED"
                else 504
                if error.code == "LLM_NORMALIZATION_TIMEOUT"
                else 502
            )
            raise ApplicationError(
                error.code,
                error.message,
                status_code=status_code,
                retryable=error.retryable,
            ) from error
        genome = build_skill_genome_from_normalized(
            material=normalized,
            original_content=content,
            title=title,
            source=source,
            license_value=license_value,
            kind=kind,
        )
        validation = validate_skill_genome(genome)
        if not validation["valid"]:
            raise ApplicationError(
                "NORMALIZED_GENOME_INVALID",
                "模型标准化结果无法生成合法 Skill Genome。",
                status_code=422,
                details=validation,
            )
        info = self.normalizer.info
        return genome, {
            "mode": info.mode,
            "provider": info.provider,
            "model": info.model,
        }


class SkillService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository

    def create_quarantine(
        self,
        genome: dict[str, Any],
        *,
        source_id: str = "manual",
        snapshot_content: str | None = None,
    ) -> dict[str, Any]:
        validation = validate_skill_genome(genome)
        if not validation["valid"]:
            raise ApplicationError(
                "INVALID_SKILL_GENOME",
                "Skill Genome 未通过 Schema 验证。",
                status_code=422,
                details=validation,
            )
        return self.repository.save_skill(
            genome, source_id=source_id, snapshot_content=snapshot_content
        )

    def benchmark(self, skill_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        skill = self.repository.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        result = run_admission_benchmark(skill["genome"])
        evaluation = self.repository.record_evaluation(skill_id, result)
        return evaluation, result

    def promote(
        self, skill_id: str, evaluation_id: str, expected_version_id: str
    ) -> dict[str, Any]:
        return self.repository.promote_to_initial(skill_id, evaluation_id, expected_version_id)


class RunService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository

    def create(self, *, seed: str, skill_id: str, mode_id: str = "stable") -> dict[str, Any]:
        skill = self.repository.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "基础 Skill 不存在。", status_code=404)
        if skill["status"] != "initial":
            raise ApplicationError(
                "INVALID_BASE_SKILL", "Evolution Run 只能使用 Initial Skill。", status_code=409
            )
        state = create_run(seed=seed, mode_id=mode_id, skill_genome=skill["genome"])
        state["replayKey"] = state["id"]
        state["id"] = f"{state['id']}-{uuid4().hex[:10]}"
        return self.repository.save_run(state, base_skill_version_id=skill["currentVersionId"])

    def get(self, run_id: str) -> dict[str, Any]:
        record = self.repository.get_run(run_id)
        if not record:
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        return record

    def _transition(self, run_id: str, revision: int, transition: Any) -> dict[str, Any]:
        record = self.get(run_id)
        if record["revision"] != revision:
            raise ApplicationError(
                "STALE_RUN_REVISION",
                "Run 已被其他操作更新。",
                status_code=409,
                details={"currentRevision": record["revision"]},
            )
        previous = record["run"]
        next_state = transition(deepcopy(previous))
        if next_state == previous:
            raise ApplicationError(
                "INVALID_RUN_TRANSITION", "当前 Run 状态不允许该操作。", status_code=409
            )
        return self.repository.save_run(
            next_state,
            base_skill_version_id=record["baseSkillVersionId"],
            expected_revision=revision,
        )

    def select_node(self, run_id: str, node_id: str, revision: int) -> dict[str, Any]:
        return self._transition(run_id, revision, lambda state: select_node(state, node_id))

    def resolve(self, run_id: str, revision: int) -> dict[str, Any]:
        return self._transition(run_id, revision, resolve_current_node)

    def choose_mutation(self, run_id: str, mutation_id: str, revision: int) -> dict[str, Any]:
        return self._transition(run_id, revision, lambda state: choose_mutation(state, mutation_id))

    def skip_mutation(self, run_id: str, revision: int) -> dict[str, Any]:
        return self._transition(run_id, revision, skip_mutation)
