from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PresetContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PresetProjectProfile(PresetContract):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    scenario: str = Field(min_length=1, max_length=500)


class PresetSourceRun(PresetContract):
    runId: str
    runRevision: int = Field(ge=1)
    seed: str
    modeId: str
    baseSkillId: str
    baseSkillVersionId: str
    mutationIds: list[str]
    evolutionIds: list[str]


class PresetAgentProfile(PresetContract):
    role: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class PresetPrimarySkill(PresetContract):
    role: Literal["primary"] = "primary"
    skillId: str
    skillVersionId: str
    genome: dict[str, Any]


class PresetWorkflowStep(PresetContract):
    id: str
    order: int = Field(ge=1)
    instruction: str = Field(min_length=1)
    tool: str | None = None
    source: str


class PresetRules(PresetContract):
    constraints: list[str] = Field(default_factory=list)
    retry: list[str] = Field(default_factory=list)
    fallback: list[str] = Field(default_factory=list)
    outputValidation: list[str] = Field(default_factory=list)


class PresetRuntimeDefaults(PresetContract):
    maxTokens: int = Field(gt=0)
    maxToolCalls: int = Field(gt=0)
    timeoutMs: int = Field(gt=0)
    priority: str
    enforceBudget: bool = True


class PresetEvaluationEvidence(PresetContract):
    mode: Literal["capability-simulation-v1", "real-finance-case-v1"] = "capability-simulation-v1"
    runtimeVerified: bool = False
    sourceRunStatus: Literal["victory"] = "victory"
    objectiveScore: float = Field(ge=0, le=100)
    encountersPassed: int = Field(ge=0)
    encounterTotal: int = Field(ge=0)
    finalStats: dict[str, float]
    benchmarkIds: list[str]


class AgentPreset(PresetContract):
    schemaVersion: Literal["0.1.0"] = "0.1.0"
    id: str
    version: Literal[1] = 1
    status: Literal["candidate"] = "candidate"
    createdAt: str
    project: PresetProjectProfile
    sourceRun: PresetSourceRun
    agent: PresetAgentProfile
    primarySkill: PresetPrimarySkill
    workflow: list[PresetWorkflowStep]
    tools: list[str]
    rules: PresetRules
    runtimeDefaults: PresetRuntimeDefaults
    evaluationEvidence: PresetEvaluationEvidence
    limitations: list[str]
    digest: str


class LoadedAgentConfig(PresetContract):
    contractVersion: Literal["0.1.0"] = "0.1.0"
    presetId: str
    presetDigest: str
    project: PresetProjectProfile
    primarySkillVersionId: str
    systemPrompt: str
    developerPrompt: str
    workflow: list[PresetWorkflowStep]
    tools: list[str]
    rules: PresetRules
    runtimeDefaults: PresetRuntimeDefaults
    runtimeVerified: bool = False
