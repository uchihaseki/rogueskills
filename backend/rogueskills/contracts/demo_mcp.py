"""Read-only MCP contracts for the browser-to-Codex Evolution demo."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DemoMcpContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class DemoMcpEmptyInput(DemoMcpContract):
    pass


class DemoMcpSkillRequest(DemoMcpContract):
    skillId: str = Field(min_length=1, max_length=160)


class DemoMcpSkillVersionRequest(DemoMcpContract):
    skillVersionId: str = Field(min_length=3, max_length=200)


class DemoMcpRunRequest(DemoMcpContract):
    runId: str = Field(min_length=1, max_length=200)


class DemoMcpRunsRequest(DemoMcpContract):
    limit: int = Field(default=10, ge=1, le=50)
    status: str | None = Field(default=None, min_length=1, max_length=32)


class DemoMcpPresetRequest(DemoMcpContract):
    presetId: str | None = Field(default=None, min_length=1, max_length=200)
    runId: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_one_reference(self) -> DemoMcpPresetRequest:
        if bool(self.presetId) == bool(self.runId):
            raise ValueError("exactly one of presetId or runId is required")
        return self


class DemoMcpSkillSummary(DemoMcpContract):
    id: str
    name: str
    description: str
    status: str
    currentVersionId: str | None = None
    sourceId: str | None = None
    category: str | None = None
    score: float | None = None


class DemoMcpInitialSkills(DemoMcpContract):
    skills: list[DemoMcpSkillSummary] = Field(default_factory=list)


class DemoMcpSkillDetail(DemoMcpContract):
    skill: dict[str, Any]


class DemoMcpSkillVersionDetail(DemoMcpContract):
    version: dict[str, Any]


class DemoMcpEvolutionRunSummary(DemoMcpContract):
    id: str
    status: str
    phase: str
    seed: str
    baseSkillId: str
    baseSkillVersionId: str | None = None
    skillName: str | None = None
    scenarioId: str | None = None
    mutationIds: list[str] = Field(default_factory=list)
    evolutionIds: list[str] = Field(default_factory=list)
    completedNodeCount: int = Field(default=0, ge=0)
    totalNodeCount: int = Field(default=0, ge=0)
    automationStatus: str | None = None
    artifactId: str | None = None
    runtimeVerified: bool = False


class DemoMcpEvolutionRuns(DemoMcpContract):
    runs: list[DemoMcpEvolutionRunSummary] = Field(default_factory=list)


class DemoMcpEvolutionRunDetail(DemoMcpContract):
    record: dict[str, Any]
    mutationDetails: list[dict[str, Any]] = Field(default_factory=list)
    evolutionDetails: list[dict[str, Any]] = Field(default_factory=list)


class DemoMcpPresetDetail(DemoMcpContract):
    preset: dict[str, Any]


class DemoMcpContext(DemoMcpContract):
    available: bool
    message: str
    skill: dict[str, Any] | None = None
    run: dict[str, Any] | None = None
    artifact: dict[str, Any] | None = None
    catalog: dict[str, Any] = Field(default_factory=dict)
