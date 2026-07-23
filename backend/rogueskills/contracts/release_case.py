from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReleaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReleaseReadinessInput(ReleaseContract):
    repository: str = Field(
        min_length=3,
        max_length=200,
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    )
    ref: str = Field(default="main", min_length=1, max_length=200)
    baseBranch: str | None = Field(default=None, min_length=1, max_length=200)
    maxPullRequests: int = Field(default=20, ge=1, le=100)


class ReleaseFinding(ReleaseContract):
    id: str
    severity: Literal["info", "warning", "blocking"]
    claim: str
    evidenceIds: list[str] = Field(default_factory=list)


class ReleaseReadinessReport(ReleaseContract):
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    id: str
    caseId: str
    stage: Literal["baseline", "evolved"]
    generatedAt: str
    skillId: str
    skillVersionId: str
    repository: dict[str, Any]
    sources: list[dict[str, Any]]
    facts: list[dict[str, Any]]
    derivedMetrics: list[dict[str, Any]]
    recommendation: Literal["ready", "review", "blocked"]
    summary: str
    findings: list[ReleaseFinding]
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    dataGaps: list[str] = Field(default_factory=list)
