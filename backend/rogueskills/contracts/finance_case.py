from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FinanceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinanceCaseInput(FinanceContract):
    ticker: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z][A-Za-z0-9.-]*$")
    asOfDate: date


class FinanceNarrativeFinding(FinanceContract):
    id: str = Field(min_length=1, max_length=80)
    kind: Literal["fact", "inference", "assumption"]
    claim: str = Field(min_length=1, max_length=1200)
    evidenceIds: list[str] = Field(min_length=1, max_length=12)

    @field_validator("evidenceIds")
    @classmethod
    def unique_evidence_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in values if item.strip()))


class FinanceNarrativeRisk(FinanceContract):
    id: str = Field(min_length=1, max_length=80)
    risk: str = Field(min_length=1, max_length=800)
    evidenceIds: list[str] = Field(default_factory=list, max_length=12)


class FinanceNarrative(FinanceContract):
    summary: str = Field(min_length=1, max_length=2400)
    findings: list[FinanceNarrativeFinding] = Field(min_length=3, max_length=16)
    risks: list[FinanceNarrativeRisk] = Field(min_length=2, max_length=12)
    dataGaps: list[str] = Field(default_factory=list, max_length=12)
    conclusionBoundary: str = Field(min_length=1, max_length=800)


class FinanceSourceEvidence(FinanceContract):
    id: str
    provider: str
    title: str
    url: str
    fetchedAt: str
    sha256: str
    contentType: str


class FinanceFact(FinanceContract):
    id: str
    metric: str
    label: str
    value: float
    unit: str
    periodStart: str | None = None
    periodEnd: str
    form: str
    filed: str
    accession: str | None = None
    factName: str
    sourceEvidenceId: str
    sourceUrl: str


class FinanceDerivedMetric(FinanceContract):
    id: str
    label: str
    value: float
    unit: str
    formula: str
    inputFactIds: list[str]
    evidenceIds: list[str]


class FinanceValuationScenario(FinanceContract):
    name: Literal["bear", "base", "bull"]
    peMultiple: float = Field(gt=0)
    impliedPriceByPe: float | None = None
    fcfYield: float = Field(gt=0, lt=1)
    impliedPriceByFcf: float | None = None


class FinanceEvaluationCase(FinanceContract):
    id: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: int = Field(gt=0)
    passed: bool
    hardGate: bool = False
    details: str
    evidenceRefs: list[str] = Field(default_factory=list)
