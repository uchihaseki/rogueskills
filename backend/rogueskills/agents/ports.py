from typing import Any, Protocol

from rogueskills.contracts.runtime import (
    EvaluationRequest,
    EvaluationResult,
    MutationProposal,
    RuntimeExecution,
)


class RuntimeAdapter(Protocol):
    async def execute(
        self,
        request: EvaluationRequest,
        genome: dict[str, Any],
        runtime_case: dict[str, Any],
    ) -> RuntimeExecution: ...


class OutputEvaluator(Protocol):
    def evaluate(
        self,
        request: EvaluationRequest,
        execution: RuntimeExecution,
        scenario: dict[str, Any],
    ) -> EvaluationResult: ...


class MutationPlanner(Protocol):
    async def propose(
        self,
        genome: dict[str, Any],
        result: EvaluationResult,
    ) -> list[MutationProposal]: ...
