from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuntimeBudget(ContractModel):
    maxTokens: int = Field(gt=0)
    maxToolCalls: int = Field(gt=0)
    timeoutMs: int = Field(gt=0)


class EvaluationRequest(ContractModel):
    contractVersion: Literal["1.0.0"] = "1.0.0"
    runId: str
    skillId: str
    skillVersionId: str
    benchmarkId: str
    scenarioPackVersion: str
    caseId: str
    split: Literal["train", "validation", "hidden"]
    seed: str
    budget: RuntimeBudget


class RuntimeUsage(ContractModel):
    inputTokens: int = Field(ge=0)
    outputTokens: int = Field(ge=0)
    toolCalls: int = Field(ge=0)
    latencyMs: int = Field(ge=0)


class RuntimeExecution(ContractModel):
    contractVersion: Literal["1.0.0"] = "1.0.0"
    executionId: str
    status: Literal["queued", "running", "succeeded", "failed", "timed_out", "cancelled"]
    output: Any = None
    traceId: str | None = None
    usage: RuntimeUsage
    error: dict[str, Any] | None = None
    runtimeVersion: str


class EvaluationMetrics(ContractModel):
    quality: float = Field(ge=0, le=100)
    coverage: float = Field(ge=0, le=100)
    latencyMs: int = Field(ge=0)
    tokenCost: int = Field(ge=0)
    securityPassed: bool


class EvaluationResult(ContractModel):
    contractVersion: Literal["1.0.0"] = "1.0.0"
    evaluationId: str
    executionId: str
    skillVersionId: str
    benchmarkId: str
    scenarioPackVersion: str
    split: Literal["train", "validation", "hidden"]
    passed: bool
    score: float = Field(ge=0, le=100)
    metrics: EvaluationMetrics
    cases: list[dict[str, Any]] = Field(default_factory=list)
    summary: str
    algorithmVersion: str


class MutationProposal(ContractModel):
    contractVersion: Literal["1.0.0"] = "1.0.0"
    id: str
    sourceSkillVersionId: str
    reason: str
    evidenceRefs: list[str]
    tradeoff: str
    complexityCost: int = Field(ge=0)
    tags: list[str]
    genomePatch: list[dict[str, Any]]
    expectedEffects: dict[str, float]
    algorithmVersion: str
