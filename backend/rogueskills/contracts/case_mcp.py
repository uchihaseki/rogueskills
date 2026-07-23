from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .finance_mcp import (
    FINANCE_MCP_REDACTED_FIELDS,
    FinanceMcpLimits,
)


class CaseMcpContract(BaseModel):
    """Strict generic MCP transport contracts for approved RogueSkills Case Packs."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class CaseMcpEmptyInput(CaseMcpContract):
    pass


class CaseMcpPackRequest(CaseMcpContract):
    casePackId: str = Field(
        min_length=3,
        max_length=80,
        pattern=r"^[a-z][a-z0-9-]{2,79}$",
    )
    casePackVersion: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
    )


class CaseMcpPreflightRequest(CaseMcpPackRequest):
    pass


class CaseMcpRunInput(CaseMcpPackRequest):
    skillId: str = Field(min_length=1, max_length=160)
    skillVersionId: str | None = Field(default=None, min_length=3, max_length=200)
    input: dict[str, Any]
    mode: Literal["live", "verified_replay"] = "live"
    replayCaseId: str | None = Field(
        default=None,
        max_length=160,
        pattern=r"^(?:case-run|finance-case)-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    autoEvolve: bool = False

    @field_validator("skillId", "skillVersionId", "replayCaseId")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_payload_and_replay(self) -> CaseMcpRunInput:
        if self.mode == "verified_replay" and not self.replayCaseId:
            raise ValueError("replayCaseId is required when mode is verified_replay")
        if self.mode == "live" and self.replayCaseId:
            raise ValueError("replayCaseId is only valid when mode is verified_replay")
        encoded = json.dumps(self.input, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > 64_000:
            raise ValueError("input exceeds the 64 KB generic MCP limit")
        if _contains_secret_key(self.input):
            raise ValueError("input must not contain credentials or provider secrets")
        return self


class CaseMcpCaseRequest(CaseMcpContract):
    caseId: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^(?:case-run|finance-case)-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )

    @field_validator("caseId")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip()


class CaseMcpReportRequest(CaseMcpCaseRequest):
    stage: Literal["baseline", "evolved", "final"] = "final"
    factOffset: int = Field(default=0, ge=0)
    factLimit: int = Field(default=40, ge=1, le=100)


class CaseMcpEvaluationRequest(CaseMcpCaseRequest):
    stage: Literal["baseline", "evolved", "final"] = "final"


class CaseMcpPackDescriptor(CaseMcpContract):
    id: str
    version: str
    ref: str
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)


class CaseMcpPackList(CaseMcpContract):
    casePacks: list[CaseMcpPackDescriptor] = Field(default_factory=list)


class CaseMcpPackDetail(CaseMcpContract):
    casePack: dict[str, Any]


class CaseMcpPreflight(CaseMcpContract):
    casePackId: str
    casePackVersion: str
    ready: bool
    runtime: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CaseMcpEvaluationSummary(CaseMcpContract):
    evaluationId: str
    benchmarkId: str
    runtimeVerified: bool
    passed: bool
    score: float = Field(ge=0, le=100)
    hardGatesPassed: bool
    failedCaseIds: list[str] = Field(default_factory=list)


class CaseMcpMutationSummary(CaseMcpContract):
    id: str
    status: Literal["testing", "accepted", "rejected"]
    reason: str
    tradeoff: str
    sourceRefresh: bool = False


class CaseMcpArtifactSummary(CaseMcpContract):
    id: str
    digest: str
    status: str
    skillVersionId: str | None = None


class CaseMcpError(CaseMcpContract):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    caseId: str | None = None
    requestId: str | None = None


class CaseMcpRunSummary(CaseMcpContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    caseId: str
    casePackId: str
    casePackVersion: str
    mode: Literal["live", "verified_replay"]
    replayCaseId: str | None = None
    skillId: str
    baseSkillVersionId: str
    evolvedSkillVersionId: str | None = None
    status: Literal["queued", "running", "succeeded", "failed"]
    phase: str
    runtimeVerified: bool
    outcome: str | None = None
    baselineScore: float | None = Field(default=None, ge=0, le=100)
    evolvedScore: float | None = Field(default=None, ge=0, le=100)
    finalScore: float | None = Field(default=None, ge=0, le=100)
    scoreDelta: float | None = None
    sourceCount: int = Field(default=0, ge=0)
    factCount: int = Field(default=0, ge=0)
    warningCount: int = Field(default=0, ge=0)
    mutation: CaseMcpMutationSummary | None = None
    comparison: dict[str, Any] | None = None
    evaluation: CaseMcpEvaluationSummary | None = None
    artifact: CaseMcpArtifactSummary | None = None
    error: CaseMcpError | None = None


class CaseMcpSourceSummary(CaseMcpContract):
    id: str
    provider: str
    url: str
    fetchedAt: str
    sha256: str
    revision: str | None = None
    status: Literal["captured", "failed", "fallback"] = "captured"
    warning: str | None = None


class CaseMcpEvaluation(CaseMcpContract):
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


class CaseMcpReportWindow(CaseMcpContract):
    totalSourceCount: int = Field(ge=0)
    returnedSourceCount: int = Field(ge=0)
    totalFactCount: int = Field(ge=0)
    returnedFactCount: int = Field(ge=0)
    factOffset: int = Field(ge=0)
    factLimit: int = Field(ge=1)
    hasMoreFacts: bool
    truncated: bool
    omittedSections: list[str] = Field(default_factory=list)
    reportBytes: int = Field(ge=0)


class CaseMcpReportEnvelope(CaseMcpContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    caseId: str
    casePackId: str
    casePackVersion: str
    stage: Literal["baseline", "evolved", "final"]
    skillId: str
    skillVersionId: str
    report: dict[str, Any]
    evaluation: CaseMcpEvaluation | None = None
    sources: list[CaseMcpSourceSummary] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    window: CaseMcpReportWindow


class CaseMcpEvaluationEnvelope(CaseMcpContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    caseId: str
    casePackId: str
    casePackVersion: str
    stage: Literal["baseline", "evolved", "final"]
    evaluation: CaseMcpEvaluation


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _contains_secret_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in FINANCE_MCP_REDACTED_FIELDS or _contains_secret_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def _evaluation_summary(value: object) -> CaseMcpEvaluationSummary | None:
    source = _mapping(value)
    if not source:
        return None
    return CaseMcpEvaluationSummary(
        evaluationId=str(source["evaluationId"]),
        benchmarkId=str(source["benchmarkId"]),
        runtimeVerified=bool(source["runtimeVerified"]),
        passed=bool(source["passed"]),
        score=float(source["score"]),
        hardGatesPassed=bool(source["hardGatesPassed"]),
        failedCaseIds=[str(item) for item in source.get("failedCaseIds", [])],
    )


def _artifact_summary(value: object) -> CaseMcpArtifactSummary | None:
    artifact = _mapping(value)
    if not artifact:
        return None
    primary_skill = _mapping(artifact.get("primarySkill"))
    return CaseMcpArtifactSummary(
        id=str(artifact["id"]),
        digest=str(artifact["digest"]),
        status=str(artifact.get("status", "candidate")),
        skillVersionId=(
            str(artifact["skillVersionId"])
            if artifact.get("skillVersionId")
            else (
                str(primary_skill["skillVersionId"])
                if primary_skill.get("skillVersionId")
                else None
            )
        ),
    )


def summarize_case_run(case: Mapping[str, Any]) -> CaseMcpRunSummary:
    final_report = _mapping(case.get("finalReport"))
    baseline = _mapping(case.get("baseline"))
    evolved = _mapping(case.get("evolved"))
    baseline_evaluation = _mapping(baseline.get("evaluation"))
    evolved_evaluation = _mapping(evolved.get("evaluation"))
    final_evaluation = _mapping(case.get("finalEvaluation"))
    mutation = _mapping(case.get("mutation"))
    comparison = case.get("comparison")
    sources = final_report.get("sources")
    facts = final_report.get("facts")
    warnings = final_report.get("warnings")
    evaluation_verified = bool(
        final_evaluation
        and final_evaluation.get("runtimeVerified")
        and final_evaluation.get("passed")
        and final_evaluation.get("hardGatesPassed")
    )
    return CaseMcpRunSummary(
        caseId=str(case["id"]),
        casePackId=str(case.get("casePackId") or "finance-stock-analysis"),
        casePackVersion=str(case.get("casePackVersion") or "1.0.0"),
        mode=case["mode"],
        replayCaseId=case.get("replayCaseId"),
        skillId=str(case["skillId"]),
        baseSkillVersionId=str(case["baseSkillVersionId"]),
        evolvedSkillVersionId=case.get("evolvedSkillVersionId"),
        status=case["status"],
        phase=str(case["phase"]),
        runtimeVerified=bool(case.get("runtimeVerified", False)) and evaluation_verified,
        outcome=(
            str(final_report["recommendation"])
            if isinstance(final_report.get("recommendation"), str)
            else None
        ),
        baselineScore=baseline_evaluation.get("score"),
        evolvedScore=evolved_evaluation.get("score"),
        finalScore=final_evaluation.get("score"),
        scoreDelta=_mapping(comparison).get("scoreDelta"),
        sourceCount=len(sources) if isinstance(sources, list) else 0,
        factCount=len(facts) if isinstance(facts, list) else 0,
        warningCount=len(warnings) if isinstance(warnings, list) else 0,
        mutation=(
            CaseMcpMutationSummary(
                id=str(mutation["id"]),
                status=mutation["status"],
                reason=str(mutation["reason"]),
                tradeoff=str(mutation["tradeoff"]),
                sourceRefresh=bool(mutation.get("sourceRefresh", False)),
            )
            if mutation
            else None
        ),
        comparison=comparison if isinstance(comparison, dict) else None,
        evaluation=_evaluation_summary(final_evaluation),
        artifact=_artifact_summary(case.get("runtimeArtifact") or case.get("agentPreset")),
        error=case_error(case),
    )


def case_error(case: Mapping[str, Any]) -> CaseMcpError | None:
    error = case.get("error")
    if not isinstance(error, Mapping):
        return None
    return CaseMcpError(
        code=str(error.get("code") or "CASE_RUN_FAILED"),
        message=str(error.get("message") or "Case Run failed."),
        retryable=bool(error.get("retryable", False)),
        details=_redact_mapping(error.get("details")),
        caseId=str(case["id"]),
    )


def _redact_mapping(value: object) -> dict[str, Any]:
    redacted = _redact(value)
    return dict(redacted) if isinstance(redacted, Mapping) else {}


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if str(key).lower() in FINANCE_MCP_REDACTED_FIELDS
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _report_for_stage(
    case: Mapping[str, Any], stage: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if stage == "final":
        return _mapping(case.get("finalReport")), _mapping(case.get("finalEvaluation"))
    section = _mapping(case.get(stage))
    return _mapping(section.get("report")), _mapping(section.get("evaluation"))


def build_case_mcp_report(
    case: Mapping[str, Any],
    stage: Literal["baseline", "evolved", "final"],
    *,
    fact_offset: int = 0,
    fact_limit: int = 40,
    limits: FinanceMcpLimits | None = None,
) -> CaseMcpReportEnvelope:
    report, evaluation = _report_for_stage(case, stage)
    if not report:
        raise ValueError(f"Case report is not available for stage: {stage}")
    active_limits = limits or FinanceMcpLimits()
    bounded_fact_limit = min(fact_limit, active_limits.maxInlineFacts)
    all_sources = report.get("sources", [])
    all_facts = report.get("facts", [])
    if not isinstance(all_sources, list) or not isinstance(all_facts, list):
        raise ValueError("Case report sources and facts must be lists")
    inline_sources = all_sources[: active_limits.maxInlineSources]
    inline_facts = all_facts[fact_offset : fact_offset + bounded_fact_limit]
    inline_report = deepcopy(dict(report))
    inline_report.pop("rawSnapshots", None)
    inline_report.pop("sourceBundle", None)
    inline_report["sources"] = inline_sources
    inline_report["facts"] = inline_facts
    omitted_sections: list[str] = []

    def report_bytes() -> int:
        return len(
            json.dumps(inline_report, ensure_ascii=False, separators=(",", ":")).encode()
        )

    while inline_facts and report_bytes() > active_limits.maxInlineReportBytes:
        inline_facts.pop()
    inline_report["facts"] = inline_facts
    protected = {
        "schemaVersion",
        "id",
        "caseId",
        "stage",
        "skillId",
        "skillVersionId",
        "sources",
        "facts",
        "summary",
        "recommendation",
        "dataGaps",
        "warnings",
    }
    while report_bytes() > active_limits.maxInlineReportBytes:
        candidates = [
            key
            for key, value in inline_report.items()
            if key not in protected and isinstance(value, (dict, list))
        ]
        if not candidates:
            break
        largest = max(
            candidates,
            key=lambda key: len(
                json.dumps(inline_report[key], ensure_ascii=False, separators=(",", ":")).encode()
            ),
        )
        inline_report.pop(largest)
        omitted_sections.append(largest)
    serialized_bytes = report_bytes()
    if serialized_bytes > active_limits.maxInlineReportBytes:
        raise ValueError("Case report identity exceeds the configured MCP inline limit")
    sources = [
        CaseMcpSourceSummary(
            id=str(source["id"]),
            provider=str(source["provider"]),
            url=str(source["url"]),
            fetchedAt=str(source["fetchedAt"]),
            sha256=str(source["sha256"]),
            revision=str(source["revision"]) if source.get("revision") is not None else None,
            status=source.get("status", "captured"),
            warning=source.get("warning"),
        )
        for source in inline_sources
    ]
    report_warnings = report.get("warnings", [])
    warnings = [item for item in report_warnings if isinstance(item, dict)] if isinstance(report_warnings, list) else []
    returned_fact_count = len(inline_facts)
    truncated = bool(
        len(inline_sources) < len(all_sources)
        or fact_offset > 0
        or fact_offset + returned_fact_count < len(all_facts)
        or omitted_sections
    )
    return CaseMcpReportEnvelope(
        caseId=str(case["id"]),
        casePackId=str(case["casePackId"]),
        casePackVersion=str(case["casePackVersion"]),
        stage=stage,
        skillId=str(report["skillId"]),
        skillVersionId=str(report["skillVersionId"]),
        report=inline_report,
        evaluation=CaseMcpEvaluation.model_validate(evaluation) if evaluation else None,
        sources=sources,
        warnings=warnings,
        window=CaseMcpReportWindow(
            totalSourceCount=len(all_sources),
            returnedSourceCount=len(inline_sources),
            totalFactCount=len(all_facts),
            returnedFactCount=returned_fact_count,
            factOffset=fact_offset,
            factLimit=bounded_fact_limit,
            hasMoreFacts=fact_offset + returned_fact_count < len(all_facts),
            truncated=truncated,
            omittedSections=omitted_sections,
            reportBytes=serialized_bytes,
        ),
    )
