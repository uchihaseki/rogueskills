from typing import Any

from rogueskills.domain.presets import InvalidAgentPreset, compile_agent_preset
from rogueskills.infrastructure.preset_repository import AgentPresetRepository
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class AgentPresetService:
    def __init__(
        self,
        skill_repository: SkillRepository,
        preset_repository: AgentPresetRepository,
    ) -> None:
        self.skills = skill_repository
        self.presets = preset_repository

    def create(
        self,
        *,
        run_id: str,
        expected_revision: int,
        project_name: str,
        project_description: str,
        scenario: str,
    ) -> tuple[dict[str, Any], bool]:
        record = self.skills.get_run(run_id)
        if not record:
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        if record["revision"] != expected_revision:
            raise ApplicationError(
                "STALE_RUN_REVISION",
                "Run 已被其他操作更新。",
                status_code=409,
                details={"currentRevision": record["revision"]},
            )

        existing = self.presets.get_by_run_id(run_id)
        if existing:
            requested_project = {
                "name": project_name.strip(),
                "description": project_description.strip(),
                "scenario": scenario.strip(),
            }
            if existing["project"] == requested_project:
                return existing, False
            raise ApplicationError(
                "AGENT_PRESET_ALREADY_EXISTS",
                "该 Run 已经生成 AgentPreset，不能覆盖不可变配置。",
                status_code=409,
                details={"presetId": existing["id"]},
            )

        run = record["run"]
        if run.get("status") != "victory" or run.get("phase") != "ended":
            raise ApplicationError(
                "RUN_NOT_VICTORIOUS",
                "只有已通关的 Evolution Run 才能生成 AgentPreset。",
                status_code=409,
            )
        version = self.skills.get_skill_version(record["baseSkillVersionId"])
        if not version or version["skillId"] != run["baseSkillId"]:
            raise ApplicationError(
                "BASE_SKILL_VERSION_NOT_FOUND",
                "Run 引用的基础 Skill Version 不存在。",
                status_code=409,
            )
        try:
            preset = compile_agent_preset(
                run=run,
                run_revision=record["revision"],
                base_skill_version_id=record["baseSkillVersionId"],
                base_skill_genome=version["genome"],
                project_name=project_name,
                project_description=project_description,
                scenario=scenario,
            )
        except InvalidAgentPreset as error:
            raise ApplicationError(
                "AGENT_PRESET_INVALID",
                str(error),
                status_code=422,
            ) from error
        return self.presets.save(preset), True

    def get(self, preset_id: str) -> dict[str, Any]:
        preset = self.presets.get(preset_id)
        if not preset:
            raise ApplicationError("AGENT_PRESET_NOT_FOUND", "AgentPreset 不存在。", status_code=404)
        return preset
