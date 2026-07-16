from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(StrictModel):
    query: str = ""
    sourceIds: list[str] = Field(default_factory=lambda: ["builtin", "github"])


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
