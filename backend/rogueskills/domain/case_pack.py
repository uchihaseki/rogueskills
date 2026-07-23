from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from rogueskills.agents.case_runtime import (
    CaseDataGateway,
    CaseEvaluator,
    CaseMutationPlanner,
    CaseRuntime,
    DatasetBuilder,
    RuntimeArtifactBuilder,
)
from rogueskills.contracts.case_runtime import CaseRuntimePolicy, CaseSkillPolicy


class CasePackRegistrationError(ValueError):
    pass


class CasePackSkillError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class CasePack:
    id: str
    version: str
    name: str
    description: str
    input_model: type[BaseModel] | None
    report_model: type[BaseModel] | None
    capabilities: tuple[str, ...]
    skill_policy: CaseSkillPolicy
    runtime_policy: CaseRuntimePolicy
    data_gateway: CaseDataGateway
    dataset_builder: DatasetBuilder
    runtime: CaseRuntime
    evaluator: CaseEvaluator
    mutation_planner: CaseMutationPlanner | None
    artifact_builder: RuntimeArtifactBuilder | None
    state_projector: Callable[[dict[str, Any]], dict[str, Any]]
    preflight_provider: Callable[[], dict[str, Any]]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{2,79}", self.id):
            raise CasePackRegistrationError(f"Invalid Case Pack ID: {self.id}")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", self.version):
            raise CasePackRegistrationError(f"Invalid Case Pack version: {self.version}")
        if not self.name.strip() or not self.description.strip():
            raise CasePackRegistrationError("Case Pack name and description are required")
        if not self.capabilities or len(set(self.capabilities)) != len(self.capabilities):
            raise CasePackRegistrationError(
                "Case Pack capabilities must be non-empty and unique"
            )

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def validate_skill(self, skill: dict[str, Any]) -> None:
        if skill.get("status") != self.skill_policy.requiredStatus:
            raise CasePackSkillError(
                "status",
                f"Case Pack requires Skill status={self.skill_policy.requiredStatus}.",
            )
        category = skill.get("genome", {}).get("metadata", {}).get("category")
        if (
            self.skill_policy.requiredCategory is not None
            and category != self.skill_policy.requiredCategory
        ):
            raise CasePackSkillError(
                "category",
                f"Case Pack requires Skill category={self.skill_policy.requiredCategory}.",
            )

    def validate_input(self, case_input: dict[str, Any]) -> dict[str, Any]:
        if self.input_model is None:
            return dict(case_input)
        return self.input_model.model_validate(case_input).model_dump(mode="json")

    def project_state(self, case_input: dict[str, Any]) -> dict[str, Any]:
        return self.state_projector(case_input)

    def preflight(self) -> dict[str, Any]:
        return self.preflight_provider()


class CasePackRegistry:
    def __init__(self) -> None:
        self._packs: dict[tuple[str, str], CasePack] = {}

    def register(self, pack: CasePack) -> CasePack:
        key = (pack.id, pack.version)
        if key in self._packs:
            raise CasePackRegistrationError(f"Case Pack already registered: {pack.ref}")
        self._packs[key] = pack
        return pack

    def get(self, pack_id: str, version: str | None = None) -> CasePack:
        if version is not None:
            pack = self._packs.get((pack_id, version))
            if pack is None:
                raise CasePackRegistrationError(f"Case Pack not found: {pack_id}@{version}")
            return pack
        matches = [pack for (candidate_id, _), pack in self._packs.items() if candidate_id == pack_id]
        if not matches:
            raise CasePackRegistrationError(f"Case Pack not found: {pack_id}")
        return sorted(matches, key=lambda item: item.version)[-1]

    def list(self) -> list[CasePack]:
        return sorted(self._packs.values(), key=lambda item: (item.id, item.version))

    def descriptors(self) -> list[dict[str, Any]]:
        return [
            {
                "id": pack.id,
                "version": pack.version,
                "ref": pack.ref,
                "name": pack.name,
                "description": pack.description,
                "capabilities": list(pack.capabilities),
            }
            for pack in self.list()
        ]
