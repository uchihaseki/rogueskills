from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CaseValidationMcpContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CaseValidationMcpEmptyInput(CaseValidationMcpContract):
    pass


class CaseValidationMcpRunRequest(CaseValidationMcpContract):
    runId: str = Field(min_length=1, max_length=160, pattern=r"^run-[A-Za-z0-9._-]+$")
    limit: int = Field(default=20, ge=1, le=100)


class CaseValidationMcpRequest(CaseValidationMcpContract):
    validationId: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^case-validation-[A-Za-z0-9._-]+$",
    )


class CaseValidationMcpValidateInput(CaseValidationMcpContract):
    runId: str = Field(min_length=1, max_length=160, pattern=r"^run-[A-Za-z0-9._-]+$")
    replayCaseId: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^(?:case-run|finance-case)-[A-Za-z0-9._-]+$",
    )
    input: dict[str, Any]
    casePackId: str = "finance-stock-analysis"
    casePackVersion: str = "1.0.0"
    mode: Literal["verified_replay"] = "verified_replay"


class CaseValidationMcpSummary(CaseValidationMcpContract):
    validationId: str
    sourceRunId: str
    candidatePresetId: str
    candidatePresetDigest: str
    casePackId: str
    casePackVersion: str
    mode: Literal["verified_replay"]
    replayCaseId: str
    baseSkillVersionId: str
    status: Literal["queued", "running", "succeeded", "failed"]
    phase: str
    baselineScore: float | None = None
    candidateScore: float | None = None
    scoreDelta: float | None = None
    repairedCaseIds: list[str] = Field(default_factory=list)
    runtimeVerified: bool
    accepted: bool
    promotionStatus: str
    promoted: bool
    evolvedSkillVersionId: str | None = None
    sourceBundleDigest: str | None = None
    datasetDigest: str | None = None
    executionPolicyDigest: str | None = None
    createdAt: str
    completedAt: str | None = None
    error: dict[str, Any] | None = None


class CaseValidationMcpList(CaseValidationMcpContract):
    validations: list[CaseValidationMcpSummary] = Field(default_factory=list)


class CaseValidationMcpDetail(CaseValidationMcpContract):
    validation: dict[str, Any]


class CaseValidationMcpComparison(CaseValidationMcpContract):
    validationId: str
    comparison: dict[str, Any]
    contributionCoverage: list[dict[str, Any]] = Field(default_factory=list)
    promotion: dict[str, Any]


class CaseValidationMcpContext(CaseValidationMcpContract):
    available: bool
    message: str
    validation: CaseValidationMcpSummary | None = None


class CaseValidationMcpDemoScript(CaseValidationMcpContract):
    available: bool
    message: str
    validationId: str | None = None
    sourceRunId: str | None = None
    evidenceMode: Literal["verified_replay"] | None = None
    businessReport: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    candidateFormation: list[dict[str, Any]] = Field(default_factory=list)
    associatedRepairs: list[dict[str, Any]] = Field(default_factory=list)
    promotion: dict[str, Any] | None = None
    talkTrack: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)


def summarize_case_validation(value: dict[str, Any]) -> CaseValidationMcpSummary:
    comparison = value.get("comparison") if isinstance(value.get("comparison"), dict) else {}
    promotion = value.get("promotion") if isinstance(value.get("promotion"), dict) else {}
    return CaseValidationMcpSummary(
        validationId=str(value["id"]),
        sourceRunId=str(value["sourceRunId"]),
        candidatePresetId=str(value["candidatePresetId"]),
        candidatePresetDigest=str(value["candidatePresetDigest"]),
        casePackId=str(value["casePackId"]),
        casePackVersion=str(value["casePackVersion"]),
        mode=value["mode"],
        replayCaseId=str(value["replayCaseId"]),
        baseSkillVersionId=str(value["baseSkillVersionId"]),
        status=value["status"],
        phase=str(value["phase"]),
        baselineScore=comparison.get("baselineScore"),
        candidateScore=comparison.get("candidateScore"),
        scoreDelta=comparison.get("scoreDelta"),
        repairedCaseIds=[str(item) for item in comparison.get("repairedCaseIds", [])],
        runtimeVerified=bool(value.get("runtimeVerified", False)),
        accepted=bool(value.get("accepted", False)),
        promotionStatus=str(promotion.get("status") or "not_eligible"),
        promoted=bool(promotion.get("promoted", False)),
        evolvedSkillVersionId=promotion.get("evolvedSkillVersionId"),
        sourceBundleDigest=value.get("sourceBundleDigest"),
        datasetDigest=value.get("datasetDigest"),
        executionPolicyDigest=value.get("executionPolicyDigest"),
        createdAt=str(value["createdAt"]),
        completedAt=value.get("completedAt"),
        error=value.get("error") if isinstance(value.get("error"), dict) else None,
    )
