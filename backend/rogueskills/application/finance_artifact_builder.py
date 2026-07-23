from __future__ import annotations

from typing import Any

from rogueskills.application.preset_service import AgentPresetService
from rogueskills.contracts.case_runtime import CaseEvaluation
from rogueskills.domain.genome import capability_profile_from_genome
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class FinanceRuntimeArtifactBuilder:
    """Preserve the existing Finance Evolution Run and AgentPreset artifact shape."""

    def __init__(self, skills: SkillRepository, presets: AgentPresetService) -> None:
        self.skills = skills
        self.presets = presets

    def build(
        self, case_run: dict[str, Any], evaluation: CaseEvaluation
    ) -> dict[str, Any]:
        final_version_id = (
            case_run.get("evolvedSkillVersionId") or case_run["baseSkillVersionId"]
        )
        final_version = self.skills.get_skill_version(final_version_id)
        if not final_version:
            raise ApplicationError(
                "FINAL_SKILL_VERSION_NOT_FOUND",
                "真实 Case 通过，但最终 Skill Version 不存在。",
                status_code=409,
            )

        case_id = str(case_run["id"])
        ticker = str(case_run["ticker"]).upper()
        as_of_date = str(case_run["asOfDate"])
        finance_run_id = f"run-real-{case_id}"
        real_run = {
            "id": finance_run_id,
            "seed": f"{ticker}-{as_of_date}",
            "modeId": "stable",
            "baseSkillId": case_run["skillId"],
            "status": "victory",
            "phase": "ended",
            "stats": capability_profile_from_genome(final_version["genome"]),
            "mutationIds": [
                case_run["mutation"]["id"]
            ]
            if case_run.get("mutation")
            else [],
            "evolutionIds": ["real_finance_runtime"],
            "encounterHistory": [
                {
                    "passed": True,
                    "benchmarkId": evaluation.benchmarkId,
                    "evaluationId": evaluation.evaluationId,
                }
            ],
            "runtimeVerification": {
                "runtimeVerified": True,
                "mode": "real-finance-case-v1",
                "caseId": case_id,
                "ticker": ticker,
                "asOfDate": as_of_date,
                "score": evaluation.score,
                "benchmarkId": evaluation.benchmarkId,
                "evaluationId": evaluation.evaluationId,
            },
        }
        saved_run = self.skills.save_run(real_run, base_skill_version_id=final_version_id)
        preset, _created = self.presets.create(
            run_id=finance_run_id,
            expected_revision=saved_run["revision"],
            project_name=f"{ticker} Evidence Finance Agent",
            project_description=(
                f"基于 {ticker} 在 {as_of_date} 前公开披露与市场数据验证通过的金融研究 Agent。"
            ),
            scenario="public-company-financial-analysis",
        )
        return {
            "financeEvolutionRunId": finance_run_id,
            "agentPreset": preset,
        }
