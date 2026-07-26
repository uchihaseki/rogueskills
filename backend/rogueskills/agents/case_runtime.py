from __future__ import annotations

from typing import Any, Protocol

from rogueskills.contracts.case_runtime import (
    CaseEvaluation,
    CaseMutationProposal,
    CaseRuntimePolicy,
    CaseSourcePolicy,
)


class CaseRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class CaseDataGateway(Protocol):
    async def fetch_live(
        self, case_input: dict[str, Any], source_policy: CaseSourcePolicy
    ) -> dict[str, Any]: ...


class DatasetBuilder(Protocol):
    def build(
        self, source_bundle: dict[str, Any], case_input: dict[str, Any]
    ) -> dict[str, Any]: ...


class CaseRuntime(Protocol):
    async def execute(
        self,
        genome: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


class PresetCaseRuntime(Protocol):
    async def execute_preset(
        self,
        preset: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        execution_policy: dict[str, Any],
    ) -> dict[str, Any]: ...


class CaseEvaluator(Protocol):
    def evaluate(
        self,
        report: dict[str, Any],
        dataset: dict[str, Any],
        policy: CaseRuntimePolicy,
    ) -> CaseEvaluation: ...


class CaseMutationPlanner(Protocol):
    def propose(
        self,
        genome: dict[str, Any],
        evaluation: CaseEvaluation,
    ) -> CaseMutationProposal: ...


class RuntimeArtifactBuilder(Protocol):
    def build(
        self,
        case_run: dict[str, Any],
        evaluation: CaseEvaluation,
    ) -> dict[str, Any]: ...


class CaseRunStore(Protocol):
    def save(
        self,
        state: dict[str, Any],
        *,
        source_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def get(
        self, case_id: str, *, include_bundle: bool = False
    ) -> dict[str, Any] | None: ...


class CaseSkillStore(Protocol):
    def save_evolved_skill(
        self,
        genome: dict[str, Any],
        *,
        expected_version_id: str,
        runtime_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class AgentPresetStore(Protocol):
    def get(self, preset_id: str) -> dict[str, Any] | None: ...
