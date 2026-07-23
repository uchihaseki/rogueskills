from __future__ import annotations

from datetime import date
from typing import Any

from rogueskills.agents.finance_analyst import FinanceAnalyst
from rogueskills.application.case_run_service import CaseRunService
from rogueskills.domain.case_pack import CasePack, CasePackSkillError
from rogueskills.infrastructure.repository import SkillRepository

from .errors import ApplicationError


class FinanceCaseService:
    """Finance compatibility facade over the generic CaseRunService."""

    def __init__(
        self,
        *,
        analyst: FinanceAnalyst,
        skills: SkillRepository,
        case_pack: CasePack,
        runner: CaseRunService,
    ) -> None:
        self.analyst = analyst
        self.skills = skills
        self.case_pack = case_pack
        self.runner = runner

    def _skill(self, skill_id: str) -> dict[str, Any]:
        skill = self.skills.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        try:
            self.case_pack.validate_skill(skill)
        except CasePackSkillError as error:
            if error.reason == "status":
                raise ApplicationError(
                    "FINANCE_CASE_REQUIRES_INITIAL_SKILL",
                    "真实金融 Case 只能使用 Initial Skill。",
                    status_code=409,
                ) from error
            raise ApplicationError(
                "FINANCE_SKILL_REQUIRED",
                "请选择 metadata.category=finance 的 Skill。",
                status_code=409,
            ) from error
        return skill

    def preflight(self) -> dict[str, Any]:
        return self.case_pack.preflight()

    async def run(
        self,
        *,
        ticker: str,
        skill_id: str,
        as_of_date: date,
        mode: str,
        replay_case_id: str | None,
        auto_evolve: bool,
    ) -> dict[str, Any]:
        if not self.analyst.info.configured:
            raise ApplicationError(
                "FINANCE_ANALYST_NOT_CONFIGURED",
                "真实金融 Case 需要配置 LLM Analyst。",
                status_code=503,
            )
        skill = self._skill(skill_id)
        normalized_ticker = ticker.upper()
        as_of_date_text = as_of_date.isoformat()
        return await self.runner.run(
            pack=self.case_pack,
            skill=skill,
            case_input={"ticker": normalized_ticker, "asOfDate": as_of_date_text},
            mode=mode,
            replay_case_id=replay_case_id,
            auto_evolve=auto_evolve,
            run_id_prefix="finance-case",
            initial_state_fields={
                "ticker": normalized_ticker,
                "asOfDate": as_of_date_text,
                "financeEvolutionRunId": None,
                "agentPreset": None,
            },
        )
