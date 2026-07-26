from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .case_runtime import CaseStageResult


class CaseValidationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CaseValidationRequest(CaseValidationContract):
    casePackId: str = Field(min_length=1, max_length=160)
    casePackVersion: str | None = Field(default=None, max_length=64)
    mode: Literal["verified_replay"] = "verified_replay"
    replayCaseId: str = Field(min_length=1, max_length=160)
    input: dict[str, Any]


class CaseValidationPromotion(CaseValidationContract):
    status: Literal[
        "not_eligible",
        "pending",
        "created",
        "version_conflict",
        "failed",
    ] = "not_eligible"
    promoted: bool = False
    evolvedSkillVersionId: str | None = None
    currentSkillVersionId: str | None = None
    error: dict[str, Any] | None = None


class CaseValidationAnalyst(CaseValidationContract):
    mode: str
    provider: str
    model: str | None = None
    configured: bool = False


class CaseValidationExecutionPolicy(CaseValidationContract):
    contractVersion: Literal["case-validation-execution-v1"] = "case-validation-execution-v1"
    timeoutMs: int = Field(ge=1_000, le=900_000)
    maxTokens: int = Field(ge=1, le=2_000_000)
    maxToolCalls: int = Field(ge=0, le=10_000)
    priority: str
    enforceBudget: bool
    temperature: float = Field(ge=0, le=2)
    analyst: CaseValidationAnalyst
    toolAuthority: Literal["case-pack"] = "case-pack"


class CaseValidationComparison(CaseValidationContract):
    baselineScore: float = Field(ge=0, le=100)
    candidateScore: float = Field(ge=0, le=100)
    scoreDelta: float
    baselinePassed: bool
    candidatePassed: bool
    baselineHardGatesPassed: bool
    candidateHardGatesPassed: bool
    baselineFailedCaseIds: list[str] = Field(default_factory=list)
    candidateFailedCaseIds: list[str] = Field(default_factory=list)
    repairedCaseIds: list[str] = Field(default_factory=list)
    regressedCaseIds: list[str] = Field(default_factory=list)
    runtimeVerified: bool
    accepted: bool


class CaseValidationContribution(CaseValidationContract):
    kind: Literal["mutation", "evolution"]
    id: str
    targetCaseIds: list[str] = Field(default_factory=list)
    repairedCaseIds: list[str] = Field(default_factory=list)
    attribution: Literal["associated_not_causal"] = "associated_not_causal"


class CaseValidationState(CaseValidationContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    id: str
    idempotencyKey: str
    sourceRunId: str
    candidatePresetId: str
    candidatePresetDigest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    casePackId: str
    casePackVersion: str
    mode: Literal["verified_replay"] = "verified_replay"
    replayCaseId: str
    demoIncluded: bool = False
    input: dict[str, Any]
    skillId: str
    baseSkillVersionId: str
    status: Literal["queued", "running", "succeeded", "failed"]
    phase: Literal[
        "queued",
        "loading_replay",
        "validating_preset",
        "building_dataset",
        "executing_baseline",
        "evaluating_baseline",
        "executing_candidate",
        "evaluating_candidate",
        "comparing",
        "promoting",
        "completed",
        "failed",
    ]
    sourceBundleDigest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    datasetDigest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    executionPolicyDigest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")
    executionPolicy: CaseValidationExecutionPolicy | None = None
    baseline: CaseStageResult | None = None
    candidate: CaseStageResult | None = None
    comparison: CaseValidationComparison | None = None
    contributionCoverage: list[CaseValidationContribution] = Field(default_factory=list)
    runtimeVerified: bool = False
    accepted: bool = False
    promotion: CaseValidationPromotion = Field(default_factory=CaseValidationPromotion)
    createdAt: str
    completedAt: str | None = None
    revision: int = Field(default=1, ge=1)
    retryOfValidationId: str | None = None
    retryCount: int = Field(default=0, ge=0)
    error: dict[str, Any] | None = None


class CaseValidationOption(CaseValidationContract):
    caseId: str
    casePackId: str
    casePackVersion: str
    mode: Literal["verified_replay"] = "verified_replay"
    sourceMode: Literal["live", "verified_replay"]
    input: dict[str, Any]
    caseLabel: str | None = None
    caseDescription: str | None = None
    ticker: str | None = None
    asOfDate: str | None = None
    sourceCount: int = Field(default=0, ge=0)
    sourceProviders: list[str] = Field(default_factory=list)
    sourceCapturedAt: str | None = None
    sourceBundleDigest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    demoIncluded: bool = False
    sourceCaseId: str | None = None
    runtimeVerified: bool = False
    createdAt: str | None = None
