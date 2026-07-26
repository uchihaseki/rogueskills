from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CaseRuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CaseSourcePolicy(CaseRuntimeContract):
    requiredProviderIds: list[str] = Field(default_factory=list, max_length=32)
    allowedHosts: list[str] = Field(default_factory=list, max_length=64)
    maxSnapshots: int = Field(default=32, ge=1, le=256)


class CaseRuntimePolicy(CaseRuntimeContract):
    maxMutationAttempts: int = Field(default=1, ge=0, le=5)
    timeoutMs: int = Field(default=180_000, ge=1_000, le=900_000)
    refreshOnFailedCaseIds: list[str] = Field(default_factory=list, max_length=32)
    sourcePolicy: CaseSourcePolicy = Field(default_factory=CaseSourcePolicy)


class CaseSkillPolicy(CaseRuntimeContract):
    requiredStatus: str = Field(default="initial", min_length=1, max_length=32)
    requiredCategory: str | None = Field(default=None, min_length=1, max_length=80)


class CaseRunInput(CaseRuntimeContract):
    casePackId: str = Field(min_length=1, max_length=160)
    casePackVersion: str | None = Field(default=None, max_length=64)
    skillId: str = Field(min_length=1, max_length=160)
    skillVersionId: str | None = Field(default=None, min_length=3, max_length=200)
    input: dict[str, Any]
    mode: Literal["live", "verified_replay"] = "live"
    replayCaseId: str | None = Field(default=None, max_length=160)
    autoEvolve: bool = False


class CaseSourceSnapshot(CaseRuntimeContract):
    id: str
    provider: str
    title: str
    url: str
    fetchedAt: str
    sha256: str
    contentType: str
    status: Literal["captured", "failed", "fallback"] = "captured"
    warning: str | None = None


class CaseEvaluation(CaseRuntimeContract):
    evaluationId: str
    benchmarkId: str
    algorithmVersion: str
    runtimeVerified: bool
    passed: bool
    score: float = Field(ge=0, le=100)
    hardGatesPassed: bool
    cases: list[dict[str, Any]] = Field(default_factory=list)
    failedCaseIds: list[str] = Field(default_factory=list)
    summary: str


class CaseMutationProposal(CaseRuntimeContract):
    id: str
    sourceSkillVersionId: str
    name: str = "Case Runtime Mutation"
    reason: str
    evidenceRefs: list[str] = Field(default_factory=list)
    tradeoff: str
    tags: list[str] = Field(default_factory=list)
    genomePatch: list[dict[str, Any]] = Field(default_factory=list)
    algorithmVersion: str


class CaseStageResult(CaseRuntimeContract):
    report: dict[str, Any]
    evaluation: CaseEvaluation


class CaseRuntimeArtifact(CaseRuntimeContract):
    id: str
    caseRunId: str
    casePackId: str
    casePackVersion: str
    skillVersionId: str
    evaluationId: str
    digest: str
    status: Literal["candidate", "approved", "revoked"] = "candidate"


class CaseRunState(CaseRuntimeContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    id: str
    casePackId: str
    casePackVersion: str
    input: dict[str, Any]
    mode: Literal["live", "verified_replay"]
    replayCaseId: str | None = None
    skillId: str
    baseSkillVersionId: str
    runtimePresetId: str | None = None
    evolvedSkillVersionId: str | None = None
    status: Literal["queued", "running", "succeeded", "failed"]
    phase: str
    runtimeVerified: bool = False
    baseline: CaseStageResult | None = None
    mutation: CaseMutationProposal | None = None
    evolved: CaseStageResult | None = None
    comparison: dict[str, Any] | None = None
    finalReport: dict[str, Any] | None = None
    finalEvaluation: CaseEvaluation | None = None
    runtimeArtifact: CaseRuntimeArtifact | None = None
    error: dict[str, Any] | None = None
