from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from rogueskills.contracts.finance_case import FinanceNarrative

from .case_runtime import CaseRuntimeError


class FinanceAnalystError(CaseRuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(code, message, retryable=retryable)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class FinanceAnalystInfo:
    mode: str
    provider: str
    model: str | None
    configured: bool


class FinanceAnalyst(Protocol):
    @property
    def info(self) -> FinanceAnalystInfo: ...

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> FinanceNarrative: ...


class UnavailableFinanceAnalyst:
    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="llm",
            provider="openai-compatible",
            model=None,
            configured=False,
        )

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> FinanceNarrative:
        del genome, case, dataset, feedback, agent_config
        raise FinanceAnalystError(
            "FINANCE_ANALYST_NOT_CONFIGURED",
            "真实金融 Case 需要配置 ROGUESKILLS_LLM_BASE_URL 和 ROGUESKILLS_LLM_MODEL。",
        )
