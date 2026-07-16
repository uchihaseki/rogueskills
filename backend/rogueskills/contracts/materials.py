from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizedMaterial(BaseModel):
    """Semantic SOP representation produced by an unprivileged LLM call."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    role: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=1000)
    instruction: str = Field(min_length=1, max_length=2000)
    steps: list[str] = Field(min_length=2, max_length=20)
    inputs: list[str] = Field(default_factory=list, max_length=12)
    outputs: list[str] = Field(default_factory=list, max_length=12)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    tools: list[str] = Field(default_factory=list, max_length=12)
    examples: list[str] = Field(default_factory=list, max_length=8)
    acceptanceCriteria: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator(
        "steps",
        "inputs",
        "outputs",
        "constraints",
        "tools",
        "examples",
        "acceptanceCriteria",
        "tags",
    )
    @classmethod
    def clean_unique_items(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = " ".join(value.split()).strip()
            if item and item not in cleaned:
                cleaned.append(item)
        return cleaned
