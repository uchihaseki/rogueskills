from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from rogueskills.domain.multi_skill import (
    InvalidMultiSkillPreset,
    compile_multi_skill_agent_preset,
)
from rogueskills.infrastructure.preset_repository import AgentPresetRepository
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class MultiSkillPresetService:
    def __init__(
        self,
        *,
        skills: SkillRepository,
        presets: AgentPresetRepository,
    ) -> None:
        self.skills = skills
        self.presets = presets

    @staticmethod
    def _merge_run_id(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"merge-run-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"

    def _source(self, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self.skills.get_run(run_id)
        if not record:
            raise ApplicationError("RUN_NOT_FOUND", "Evolution Run 不存在。", status_code=404)
        if record["run"].get("status") != "victory" or record["run"].get("phase") != "ended":
            raise ApplicationError(
                "RUN_NOT_VICTORIOUS",
                "只有已完成 Victory 的 Evolution Run 可以参与 Multi-Skill Merge。",
                status_code=409,
                details={"runId": run_id},
            )
        preset = self.presets.get_by_run_id(run_id)
        if not preset:
            raise ApplicationError(
                "AGENT_PRESET_NOT_AVAILABLE",
                "参与合并的 Evolution Run 尚未生成 AgentPreset。",
                status_code=409,
                details={"runId": run_id},
            )
        return record, preset

    def create(
        self,
        *,
        primary_run_id: str,
        primary_role: str,
        supporting_runs: list[dict[str, str]],
        routing: list[dict[str, Any]],
        project_name: str,
        project_description: str,
        scenario: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        source_signature = {
            "primaryRunId": primary_run_id,
            "primaryRole": primary_role,
            "supportingRuns": supporting_runs,
            "routing": routing,
            "project": {
                "name": project_name,
                "description": project_description,
                "scenario": scenario,
            },
        }
        merge_run_id = self._merge_run_id(source_signature)
        existing_run = self.skills.get_run(merge_run_id)
        existing_preset = self.presets.get_by_run_id(merge_run_id)
        if existing_run and existing_preset:
            return existing_run, existing_preset, False

        primary_record, primary_preset = self._source(primary_run_id)
        supporting_sources: list[dict[str, Any]] = []
        supporting_records: list[dict[str, Any]] = []
        for item in supporting_runs:
            record, preset = self._source(item["runId"])
            supporting_records.append(record)
            supporting_sources.append({"role": item["role"], "preset": preset})

        if existing_run is None:
            merge_state = deepcopy(primary_record["run"])
            source_records = [primary_record, *supporting_records]
            mutation_ids = list(
                dict.fromkeys(
                    str(item)
                    for record in source_records
                    for item in record["run"].get("mutationIds", [])
                )
            )
            evolution_ids = list(
                dict.fromkeys(
                    str(item)
                    for record in source_records
                    for item in record["run"].get("evolutionIds", [])
                )
            )
            merge_state.update(
                {
                    "id": merge_run_id,
                    "seed": f"MULTI-SKILL-MERGE:{merge_run_id}",
                    "status": "victory",
                    "phase": "ended",
                    "mutationIds": mutation_ids,
                    "evolutionIds": evolution_ids,
                    "automation": {
                        "status": "completed",
                        "selectedMonsterIds": [],
                        "project": {
                            "name": project_name,
                            "description": project_description,
                            "scenario": scenario,
                        },
                    },
                    "composition": {
                        "strategy": "orchestrated-sequential-v1",
                        "primaryRunId": primary_run_id,
                        "primaryRole": primary_role,
                        "supportingRuns": deepcopy(supporting_runs),
                        "routingRuleIds": [str(item["id"]) for item in routing],
                    },
                }
            )
            logs = list(merge_state.get("logs", []))
            logs.append(
                {
                    "id": len(logs) + 1,
                    "act": 4,
                    "message": (
                        f"Multi-Skill Merge completed with {1 + len(supporting_runs)} "
                        "victorious source Skills."
                    ),
                    "tone": "evolution",
                }
            )
            merge_state["logs"] = logs
            merge_record = self.skills.save_run(
                merge_state,
                base_skill_version_id=primary_record["baseSkillVersionId"],
            )
        else:
            merge_record = existing_run

        try:
            preset = compile_multi_skill_agent_preset(
                merge_run=merge_record["run"],
                merge_run_revision=merge_record["revision"],
                primary_role=primary_role,
                primary_preset=primary_preset,
                supporting_presets=supporting_sources,
                routing=routing,
                project_name=project_name,
                project_description=project_description,
                scenario=scenario,
            )
        except InvalidMultiSkillPreset as error:
            raise ApplicationError(
                "MULTI_SKILL_PRESET_INVALID",
                str(error),
                status_code=422,
            ) from error
        return merge_record, self.presets.save(preset), True
