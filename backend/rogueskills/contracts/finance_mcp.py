from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .finance_case import FinanceEvaluationCase

FINANCE_MCP_REDACTED_FIELDS = frozenset(
    {"authorization", "cookie", "x-api-key", "apikey", "api_key", "token"}
)


class FinanceMcpContract(BaseModel):
    """Strict transport contracts shared by the future MCP Bridge."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class FinanceMcpAnalyzeStockInput(FinanceMcpContract):
    ticker: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9.-]*$")
    asOfDate: date
    skillId: str | None = Field(default=None, min_length=1, max_length=160)
    mode: Literal["live", "verified_replay"] = "live"
    replayCaseId: str | None = Field(
        default=None,
        max_length=160,
        pattern=r"^finance-case-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    autoEvolve: bool = False

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("skillId", "replayCaseId")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_replay_reference(self) -> FinanceMcpAnalyzeStockInput:
        if self.mode == "verified_replay" and not self.replayCaseId:
            raise ValueError("replayCaseId is required when mode is verified_replay")
        if self.mode == "live" and self.replayCaseId:
            raise ValueError("replayCaseId is only valid when mode is verified_replay")
        return self


class FinanceMcpReportRequest(FinanceMcpContract):
    caseId: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^finance-case-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    stage: Literal["baseline", "evolved", "final"] = "final"
    factOffset: int = Field(default=0, ge=0)
    factLimit: int = Field(default=40, ge=1, le=100)

    @field_validator("caseId")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip()


class FinanceMcpCaseRequest(FinanceMcpContract):
    caseId: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^finance-case-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )

    @field_validator("caseId")
    @classmethod
    def normalize_case_id(cls, value: str) -> str:
        return value.strip()


class FinanceMcpPreflightInput(FinanceMcpContract):
    pass


class FinanceMcpAnalystStatus(FinanceMcpContract):
    mode: str
    provider: str
    model: str
    configured: bool


class FinanceMcpSourceStatus(FinanceMcpContract):
    id: str
    name: str
    configured: bool
    reachable: bool | None = None
    state: str | None = None


class FinanceMcpPreflight(FinanceMcpContract):
    ready: bool
    runtime: str
    analyst: FinanceMcpAnalystStatus
    sources: list[FinanceMcpSourceStatus]


class FinanceMcpSourceSummary(FinanceMcpContract):
    id: str
    provider: str
    url: str
    fetchedAt: str
    sha256: str
    status: Literal["captured", "failed", "fallback"] = "captured"
    warning: str | None = None


class FinanceMcpWarning(FinanceMcpContract):
    code: str
    message: str
    retryable: bool = False


class FinanceMcpEvaluation(FinanceMcpContract):
    evaluationId: str
    benchmarkId: str
    algorithmVersion: str
    runtimeVerified: bool
    passed: bool
    score: float = Field(ge=0, le=100)
    hardGatesPassed: bool
    cases: list[FinanceEvaluationCase]
    failedCaseIds: list[str] = Field(default_factory=list)
    summary: str


class FinanceMcpEvaluationSummary(FinanceMcpContract):
    evaluationId: str
    benchmarkId: str
    runtimeVerified: bool
    passed: bool
    score: float = Field(ge=0, le=100)
    hardGatesPassed: bool
    failedCaseIds: list[str] = Field(default_factory=list)


class FinanceMcpComparison(FinanceMcpContract):
    baselineScore: float = Field(ge=0, le=100)
    evolvedScore: float = Field(ge=0, le=100)
    scoreDelta: float
    accepted: bool
    baselineFailedCaseIds: list[str] = Field(default_factory=list)
    evolvedFailedCaseIds: list[str] = Field(default_factory=list)


class FinanceMcpMutationSummary(FinanceMcpContract):
    id: str
    status: Literal["testing", "accepted", "rejected"]
    reason: str
    tradeoff: str
    sourceRefresh: bool = False


class FinanceMcpPresetSummary(FinanceMcpContract):
    id: str
    digest: str
    status: str
    skillVersionId: str
    runtimeVerified: bool


class FinanceMcpError(FinanceMcpContract):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    caseId: str | None = None
    requestId: str | None = None


class FinanceMcpLimits(FinanceMcpContract):
    preflightTimeoutMs: int = Field(default=10_000, ge=1_000, le=60_000)
    readTimeoutMs: int = Field(default=30_000, ge=1_000, le=120_000)
    caseExecutionTimeoutMs: int = Field(default=420_000, ge=30_000, le=900_000)
    maxInlineReportBytes: int = Field(default=256_000, ge=16_000, le=2_000_000)
    maxInlineSources: int = Field(default=20, ge=1, le=100)
    maxInlineFacts: int = Field(default=100, ge=1, le=1_000)


class FinanceMcpRunSummary(FinanceMcpContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    caseId: str
    ticker: str
    asOfDate: date
    mode: Literal["live", "verified_replay"]
    skillId: str
    baseSkillVersionId: str
    evolvedSkillVersionId: str | None = None
    status: Literal["running", "succeeded", "failed"]
    phase: str
    runtimeVerified: bool
    baselineScore: float | None = Field(default=None, ge=0, le=100)
    evolvedScore: float | None = Field(default=None, ge=0, le=100)
    finalScore: float | None = Field(default=None, ge=0, le=100)
    scoreDelta: float | None = None
    sourceCount: int = Field(default=0, ge=0)
    factCount: int = Field(default=0, ge=0)
    warningCount: int = Field(default=0, ge=0)
    mutation: FinanceMcpMutationSummary | None = None
    comparison: FinanceMcpComparison | None = None
    evaluation: FinanceMcpEvaluationSummary | None = None
    agentPreset: FinanceMcpPresetSummary | None = None
    error: FinanceMcpError | None = None


class FinanceMcpReportWindow(FinanceMcpContract):
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


class FinanceMcpReportEnvelope(FinanceMcpContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    caseId: str
    stage: Literal["baseline", "evolved", "final"]
    skillId: str
    skillVersionId: str
    report: dict[str, Any]
    evaluation: FinanceMcpEvaluation | None = None
    sources: list[FinanceMcpSourceSummary] = Field(default_factory=list)
    warnings: list[FinanceMcpWarning] = Field(default_factory=list)
    window: FinanceMcpReportWindow


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _evaluation_summary(value: object) -> FinanceMcpEvaluationSummary | None:
    if not isinstance(value, Mapping) or not value:
        return None
    return FinanceMcpEvaluationSummary(
        evaluationId=str(value["evaluationId"]),
        benchmarkId=str(value["benchmarkId"]),
        runtimeVerified=bool(value["runtimeVerified"]),
        passed=bool(value["passed"]),
        score=float(value["score"]),
        hardGatesPassed=bool(value["hardGatesPassed"]),
        failedCaseIds=[str(item) for item in value.get("failedCaseIds", [])],
    )


def summarize_finance_case(case: Mapping[str, Any]) -> FinanceMcpRunSummary:
    """Convert a persisted Finance Case into a context-sized MCP summary."""

    final_report = _mapping(case.get("finalReport"))
    baseline = _mapping(case.get("baseline"))
    evolved = _mapping(case.get("evolved"))
    baseline_evaluation = _mapping(baseline.get("evaluation"))
    evolved_evaluation = _mapping(evolved.get("evaluation"))
    final_evaluation = _mapping(case.get("finalEvaluation"))
    comparison = case.get("comparison")
    mutation = _mapping(case.get("mutation"))
    preset = _mapping(case.get("agentPreset"))
    error = case.get("error")
    report_sources = final_report.get("sources")
    report_facts = final_report.get("facts")
    evaluation_verified = bool(
        final_evaluation
        and final_evaluation.get("runtimeVerified")
        and final_evaluation.get("passed")
        and final_evaluation.get("hardGatesPassed")
    )
    return FinanceMcpRunSummary(
        caseId=str(case["id"]),
        ticker=str(case["ticker"]).upper(),
        asOfDate=date.fromisoformat(str(case["asOfDate"])),
        mode=case["mode"],
        skillId=str(case["skillId"]),
        baseSkillVersionId=str(case["baseSkillVersionId"]),
        evolvedSkillVersionId=case.get("evolvedSkillVersionId"),
        status=case["status"],
        phase=str(case["phase"]),
        runtimeVerified=bool(case.get("runtimeVerified", False)) and evaluation_verified,
        baselineScore=baseline_evaluation.get("score"),
        evolvedScore=evolved_evaluation.get("score"),
        finalScore=final_evaluation.get("score"),
        scoreDelta=_mapping(comparison).get("scoreDelta"),
        sourceCount=len(report_sources) if isinstance(report_sources, list) else 0,
        factCount=len(report_facts) if isinstance(report_facts, list) else 0,
        warningCount=len(final_report.get("warnings", []))
        if isinstance(final_report.get("warnings"), list)
        else 0,
        mutation=(
            FinanceMcpMutationSummary(
                id=str(mutation["id"]),
                status=mutation["status"],
                reason=str(mutation["reason"]),
                tradeoff=str(mutation["tradeoff"]),
                sourceRefresh=bool(mutation.get("sourceRefresh", False)),
            )
            if mutation
            else None
        ),
        comparison=comparison,
        evaluation=_evaluation_summary(final_evaluation),
        agentPreset=summarize_finance_preset(
            preset,
            fallback_skill_version_id=str(
                case.get("evolvedSkillVersionId") or case["baseSkillVersionId"]
            ),
        )
        if preset
        else None,
        error=finance_mcp_error_from_api({"error": error}) if error else None,
    )


def summarize_finance_preset(
    preset: Mapping[str, Any], *, fallback_skill_version_id: str | None = None
) -> FinanceMcpPresetSummary:
    primary_skill = _mapping(preset.get("primarySkill"))
    evaluation_evidence = _mapping(preset.get("evaluationEvidence"))
    skill_version_id = primary_skill.get("skillVersionId") or fallback_skill_version_id
    if not skill_version_id:
        raise ValueError("AgentPreset does not identify a primary Skill Version")
    return FinanceMcpPresetSummary(
        id=str(preset["id"]),
        digest=str(preset["digest"]),
        status=str(preset.get("status", "candidate")),
        skillVersionId=str(skill_version_id),
        runtimeVerified=bool(evaluation_evidence.get("runtimeVerified", False)),
    )


def _report_for_stage(case: Mapping[str, Any], stage: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if stage == "final":
        return _mapping(case.get("finalReport")), _mapping(case.get("finalEvaluation"))
    section = _mapping(case.get(stage))
    return _mapping(section.get("report")), _mapping(section.get("evaluation"))


def build_finance_mcp_report(
    case: Mapping[str, Any],
    stage: Literal["baseline", "evolved", "final"],
    *,
    fact_offset: int = 0,
    fact_limit: int = 40,
    limits: FinanceMcpLimits | None = None,
) -> FinanceMcpReportEnvelope:
    """Build a stage-aware report envelope without changing the persisted report."""

    report, evaluation = _report_for_stage(case, stage)
    if not report:
        raise ValueError(f"Finance report is not available for stage: {stage}")
    active_limits = limits or FinanceMcpLimits()
    bounded_fact_limit = min(fact_limit, active_limits.maxInlineFacts)
    all_sources = report.get("sources", [])
    all_facts = report.get("facts", [])
    if not isinstance(all_sources, list) or not isinstance(all_facts, list):
        raise ValueError("Finance report sources and facts must be lists")
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
    if report_bytes() > active_limits.maxInlineReportBytes and "filings" in inline_report:
        inline_report.pop("filings")
        omitted_sections.append("filings")
    if report_bytes() > active_limits.maxInlineReportBytes:
        narrative = _mapping(inline_report.get("narrative"))
        inline_report["narrative"] = {
            "summary": narrative.get("summary", "Report detail omitted by MCP context limit."),
            "dataGaps": narrative.get("dataGaps", []),
            "conclusionBoundary": narrative.get("conclusionBoundary", ""),
        }
        omitted_sections.append("narrative.findings_and_risks")
    serialized_bytes = report_bytes()
    if serialized_bytes > active_limits.maxInlineReportBytes:
        raise ValueError("Finance report identity exceeds the configured MCP inline limit")

    sources = [
        FinanceMcpSourceSummary(
            id=str(source["id"]),
            provider=str(source["provider"]),
            url=str(source["url"]),
            fetchedAt=str(source["fetchedAt"]),
            sha256=str(source["sha256"]),
            status="captured",
        )
        for source in inline_sources
    ]
    warnings = [FinanceMcpWarning.model_validate(item) for item in report.get("warnings", [])]
    returned_fact_count = len(inline_facts)
    truncated = bool(
        len(inline_sources) < len(all_sources)
        or fact_offset > 0
        or fact_offset + returned_fact_count < len(all_facts)
        or omitted_sections
    )
    return FinanceMcpReportEnvelope(
        caseId=str(case["id"]),
        stage=stage,
        skillId=str(report["skillId"]),
        skillVersionId=str(report["skillVersionId"]),
        report=inline_report,
        evaluation=FinanceMcpEvaluation.model_validate(evaluation) if evaluation else None,
        sources=sources,
        warnings=warnings,
        window=FinanceMcpReportWindow(
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


def finance_mcp_error_from_api(
    payload: object,
    *,
    status_code: int | None = None,
    request_id: str | None = None,
) -> FinanceMcpError:
    """Normalize RogueSkills API errors and upstream failures for MCP clients."""

    body = _mapping(payload)
    raw_error = _mapping(body.get("error"))
    code = str(raw_error.get("code") or "UPSTREAM_ERROR")
    message = str(raw_error.get("message") or "RogueSkills API request failed.")
    raw_details = raw_error.get("details")
    redacted_details = _redact(raw_details) if isinstance(raw_details, Mapping) else {}
    details = dict(redacted_details) if isinstance(redacted_details, Mapping) else {}
    case_id = details.get("caseId") or body.get("caseId")
    if status_code is not None:
        details.setdefault("statusCode", status_code)
    return FinanceMcpError(
        code=code,
        message=message,
        retryable=bool(raw_error.get("retryable", False)),
        details=details,
        caseId=str(case_id) if case_id else None,
        requestId=request_id or (str(body["requestId"]) if body.get("requestId") else None),
    )
