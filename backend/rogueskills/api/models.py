from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(StrictModel):
    query: str = ""
    sourceIds: list[str] = Field(default_factory=lambda: ["builtin", "github"])


class DiscoverySearchRunRequest(StrictModel):
    query: str = Field(min_length=2, max_length=1000)
    providerIds: list[str] = Field(
        default_factory=lambda: ["github", "brave", "tavily", "exa"],
        min_length=1,
        max_length=4,
    )
    scopeIds: list[str] = Field(default_factory=lambda: ["all_web_skills"], max_length=8)
    includeLocalExamples: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class DiscoveryWarningAcknowledgement(StrictModel):
    candidateId: str
    code: str


class DiscoveryImportBatchRequest(StrictModel):
    searchRunId: str
    candidateIds: list[str] = Field(min_length=1, max_length=30)
    expectedRunRevision: int = Field(ge=1)
    acknowledgedWarnings: list[DiscoveryWarningAcknowledgement] = Field(default_factory=list)


class ImportRequest(StrictModel):
    candidate: dict[str, Any]


class MaterialConvertRequest(StrictModel):
    title: str | None = None
    content: str = Field(min_length=1, max_length=120_000)
    source: dict[str, Any] | None = None
    license: str = "unknown"
    kind: str = "sop"


class StoreSkillRequest(StrictModel):
    genome: dict[str, Any]
    sourceId: str = "manual"
    snapshotContent: str | None = None


class PromoteRequest(StrictModel):
    evaluationId: str
    expectedSkillVersionId: str


class CreateRunRequest(StrictModel):
    seed: str
    skillId: str
    modeId: str = "stable"


class RunRevisionRequest(StrictModel):
    expectedRevision: int = Field(ge=1)


class SelectNodeRequest(RunRevisionRequest):
    nodeId: str


class ChooseMutationRequest(RunRevisionRequest):
    mutationId: str


class StartAutomaticRunRequest(RunRevisionRequest):
    selectedMonsterIds: list[str] = Field(min_length=1, max_length=12)
    projectName: str = Field(min_length=1, max_length=160)
    projectDescription: str = Field(min_length=1, max_length=2000)
    scenario: str = Field(min_length=1, max_length=500)


class CreateAgentPresetRequest(RunRevisionRequest):
    projectName: str = Field(min_length=1, max_length=160)
    projectDescription: str = Field(min_length=1, max_length=2000)
    scenario: str = Field(min_length=1, max_length=500)


class MultiSkillSupportingRun(StrictModel):
    role: str = Field(min_length=1, max_length=80)
    runId: str = Field(min_length=1, max_length=160)


class MultiSkillRoutingRule(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    order: int = Field(ge=1)
    when: str = Field(min_length=1, max_length=500)
    useSkillRole: str = Field(min_length=1, max_length=80)
    instruction: str = Field(min_length=1, max_length=1000)
    fallbackSkillRole: str | None = Field(default=None, max_length=80)


class CreateMultiSkillPresetRequest(StrictModel):
    primaryRunId: str = Field(min_length=1, max_length=160)
    primaryRole: str = Field(min_length=1, max_length=80)
    supportingRuns: list[MultiSkillSupportingRun] = Field(min_length=1, max_length=8)
    routing: list[MultiSkillRoutingRule] = Field(min_length=1, max_length=24)
    projectName: str = Field(min_length=1, max_length=160)
    projectDescription: str = Field(min_length=1, max_length=2000)
    scenario: str = Field(min_length=1, max_length=500)


class FinanceBootstrapRequest(StrictModel):
    maxCommunitySkills: int = Field(default=2, ge=1, le=5)
    sopIds: list[str] | None = None
    autoPromote: bool = True


class AwesomeFinanceImportRequest(StrictModel):
    skillNames: list[str] | None = Field(default=None, max_length=20)
    autoPromote: bool = True


class CreateFinanceCaseRequest(StrictModel):
    ticker: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9.-]*$")
    skillId: str = Field(min_length=1, max_length=160)
    asOfDate: date | None = None
    mode: Literal["live", "verified_replay"] = "live"
    replayCaseId: str | None = Field(default=None, max_length=160)
    autoEvolve: bool = True


class CreateCaseRunRequest(StrictModel):
    casePackId: str = Field(min_length=1, max_length=160)
    casePackVersion: str | None = Field(default=None, max_length=64)
    skillId: str = Field(min_length=1, max_length=160)
    skillVersionId: str | None = Field(default=None, min_length=3, max_length=200)
    input: dict[str, Any]
    mode: Literal["live", "verified_replay"] = "live"
    replayCaseId: str | None = Field(default=None, max_length=160)
    autoEvolve: bool = False


class ReplayCaseRunRequest(StrictModel):
    skillId: str = Field(min_length=1, max_length=160)
    skillVersionId: str | None = Field(default=None, min_length=3, max_length=200)
    autoEvolve: bool = False


class CreateCaseValidationRequest(StrictModel):
    casePackId: str = Field(min_length=1, max_length=160)
    casePackVersion: str | None = Field(default=None, max_length=64)
    mode: Literal["verified_replay"] = "verified_replay"
    replayCaseId: str = Field(min_length=1, max_length=160)
    input: dict[str, Any]
    retryFailed: bool = False
