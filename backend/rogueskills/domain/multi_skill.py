from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from rogueskills.contracts.presets import AgentPreset

from .genome import validate_skill_genome
from .presets import agent_preset_digest
from .shared import round_number


class InvalidMultiSkillPreset(ValueError):
    pass


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _validated_source(preset: dict[str, Any]) -> dict[str, Any]:
    validated = AgentPreset.model_validate(preset).model_dump(mode="json")
    if agent_preset_digest(validated) != validated["digest"]:
        raise InvalidMultiSkillPreset(
            f"Source AgentPreset digest verification failed: {validated['id']}"
        )
    if validated.get("multiSkill"):
        raise InvalidMultiSkillPreset("Nested multi-Skill presets are not supported.")
    genome = validated["primarySkill"]["genome"]
    validation = validate_skill_genome(genome)
    if not validation["valid"]:
        raise InvalidMultiSkillPreset(
            f"Source Skill Genome is invalid: {validated['primarySkill']['skillId']}"
        )
    if genome.get("risk", {}).get("level") == "high":
        raise InvalidMultiSkillPreset("A high-risk Skill cannot enter a multi-Skill preset.")
    return validated


def _average_stats(presets: list[dict[str, Any]]) -> dict[str, float]:
    keys = _unique(
        [
            str(key)
            for preset in presets
            for key in preset["evaluationEvidence"].get("finalStats", {})
        ]
    )
    return {
        key: round_number(
            sum(
                float(preset["evaluationEvidence"].get("finalStats", {}).get(key, 0))
                for preset in presets
            )
            / len(presets),
            1,
        )
        for key in keys
    }


def compile_multi_skill_agent_preset(
    *,
    merge_run: dict[str, Any],
    merge_run_revision: int,
    primary_role: str,
    primary_preset: dict[str, Any],
    supporting_presets: list[dict[str, Any]],
    routing: list[dict[str, Any]],
    project_name: str,
    project_description: str,
    scenario: str,
    clock: Any | None = None,
) -> dict[str, Any]:
    """Compile victorious single-Skill presets into one routed candidate.

    ``supporting_presets`` items contain ``role`` and ``preset``.  Every source
    preset remains immutable; the resulting preset records its full lineage and
    starts with capability-simulation evidence until a CaseValidation verifies
    the composed runtime on a real replay.
    """

    if merge_run.get("status") != "victory" or merge_run.get("phase") != "ended":
        raise InvalidMultiSkillPreset("Only a completed victory merge Run is valid.")
    normalized_primary_role = " ".join(primary_role.split()).strip()
    if not normalized_primary_role:
        raise InvalidMultiSkillPreset("The primary Skill role is required.")
    primary = _validated_source(primary_preset)
    if not supporting_presets:
        raise InvalidMultiSkillPreset("At least one supporting Skill preset is required.")
    if merge_run.get("baseSkillId") != primary["primarySkill"]["skillId"]:
        raise InvalidMultiSkillPreset("Merge Run and primary Skill lineage do not match.")

    supports: list[tuple[str, dict[str, Any]]] = []
    roles = [normalized_primary_role]
    skill_ids = [str(primary["primarySkill"]["skillId"])]
    for item in supporting_presets:
        role = " ".join(str(item.get("role") or "").split()).strip()
        if not role:
            raise InvalidMultiSkillPreset("Every supporting Skill needs a role.")
        source = _validated_source(dict(item.get("preset") or {}))
        skill_id = str(source["primarySkill"]["skillId"])
        if role in roles:
            raise InvalidMultiSkillPreset(f"Duplicate Skill role: {role}")
        if skill_id in skill_ids:
            raise InvalidMultiSkillPreset(f"Duplicate Skill in composition: {skill_id}")
        roles.append(role)
        skill_ids.append(skill_id)
        supports.append((role, source))

    normalized_routing = sorted(deepcopy(routing), key=lambda item: int(item.get("order", 0)))
    if not normalized_routing:
        raise InvalidMultiSkillPreset("At least one routing rule is required.")
    route_ids: list[str] = []
    route_orders: list[int] = []
    for route in normalized_routing:
        route_id = str(route.get("id") or "").strip()
        order = int(route.get("order") or 0)
        target = str(route.get("useSkillRole") or "")
        fallback = route.get("fallbackSkillRole")
        if not route_id or route_id in route_ids:
            raise InvalidMultiSkillPreset("Routing rule ids must be non-empty and unique.")
        if order < 1 or order in route_orders:
            raise InvalidMultiSkillPreset("Routing rule orders must be positive and unique.")
        if target not in roles or (fallback is not None and str(fallback) not in roles):
            raise InvalidMultiSkillPreset(f"Routing rule references an unknown role: {route_id}")
        route_ids.append(route_id)
        route_orders.append(order)

    sources = [primary, *[preset for _, preset in supports]]
    source_run_ids = _unique([str(item["sourceRun"]["runId"]) for item in sources])
    if len(source_run_ids) != len(sources):
        raise InvalidMultiSkillPreset("Every composed Skill must come from a distinct source Run.")

    supporting_skills = [
        {
            "role": role,
            "skillId": preset["primarySkill"]["skillId"],
            "skillVersionId": preset["primarySkill"]["skillVersionId"],
            "sourceRunId": preset["sourceRun"]["runId"],
            "sourcePresetId": preset["id"],
            "sourcePresetDigest": preset["digest"],
            "genome": deepcopy(preset["primarySkill"]["genome"]),
        }
        for role, preset in supports
    ]
    conflict_policy = [
        "Case Pack source authority overrides individual Skill tool preferences.",
        "Hard safety constraints are additive and cannot be removed by another Skill.",
        "Duplicate workflow instructions are executed once; evidence lineage is retained.",
        "The report-synthesis role may summarize evidence but may not create new facts.",
    ]

    workflow: list[dict[str, Any]] = []
    known_instructions: set[str] = set()
    role_sources = [(normalized_primary_role, primary), *supports]
    for role, preset in role_sources:
        genome = preset["primarySkill"]["genome"]
        declaration = (
            f"Activate the {role} role using Skill {preset['primarySkill']['skillId']} "
            f"for: {genome.get('description') or preset['agent']['objective']}"
        )
        workflow.append(
            {
                "id": f"multi-step-{len(workflow) + 1}",
                "order": len(workflow) + 1,
                "instruction": declaration,
                "tool": None,
                "source": f"skill:{role}:{preset['primarySkill']['skillVersionId']}",
            }
        )
        for step in preset.get("workflow", []):
            instruction = " ".join(str(step.get("instruction") or "").split()).strip()
            if not instruction or instruction in known_instructions:
                continue
            known_instructions.add(instruction)
            workflow.append(
                {
                    "id": f"multi-step-{len(workflow) + 1}",
                    "order": len(workflow) + 1,
                    "instruction": instruction,
                    "tool": step.get("tool"),
                    "source": f"skill:{role}:{preset['primarySkill']['skillVersionId']}",
                }
            )

    rules = {
        key: _unique([str(value) for preset in sources for value in preset["rules"][key]])
        for key in ("constraints", "retry", "fallback", "outputValidation")
    }
    rules["constraints"] = _unique([*rules["constraints"], *conflict_policy])
    tools = _unique([str(tool) for preset in sources for tool in preset.get("tools", [])])
    defaults = [preset["runtimeDefaults"] for preset in sources]
    runtime_defaults = {
        "maxTokens": max(int(item["maxTokens"]) for item in defaults),
        "maxToolCalls": max(1, sum(int(item["maxToolCalls"]) for item in defaults)),
        "timeoutMs": max(int(item["timeoutMs"]) for item in defaults),
        "priority": "quality" if any(item["priority"] == "quality" for item in defaults) else defaults[0]["priority"],
        "enforceBudget": all(bool(item.get("enforceBudget", True)) for item in defaults),
    }
    evidence_items = [preset["evaluationEvidence"] for preset in sources]
    objective_score = round_number(
        sum(float(item["objectiveScore"]) for item in evidence_items) / len(evidence_items),
        1,
    )
    route_lines = [
        f"- {item['when']} -> {item['useSkillRole']}: {item['instruction']}"
        for item in normalized_routing
    ]
    instruction = (
        f"{primary['agent']['instruction']}\n\n"
        "Multi-Skill orchestration routes:\n"
        + "\n".join(route_lines)
        + "\n\nApply the conflict policy before producing the final answer."
    )
    timestamp = (clock or (lambda: datetime.now(UTC)))().isoformat().replace("+00:00", "Z")
    preset_id = f"preset-{hashlib.sha256(str(merge_run['id']).encode('utf-8')).hexdigest()[:20]}"
    mutation_ids = _unique(
        [str(item) for preset in sources for item in preset["sourceRun"].get("mutationIds", [])]
    )
    evolution_ids = _unique(
        [str(item) for preset in sources for item in preset["sourceRun"].get("evolutionIds", [])]
    )
    payload: dict[str, Any] = {
        "schemaVersion": "0.1.0",
        "id": preset_id,
        "version": 1,
        "status": "candidate",
        "createdAt": timestamp,
        "project": {
            "name": project_name.strip(),
            "description": project_description.strip(),
            "scenario": scenario.strip(),
        },
        "sourceRun": {
            "runId": str(merge_run["id"]),
            "runRevision": merge_run_revision,
            "seed": str(merge_run["seed"]),
            "modeId": str(merge_run["modeId"]),
            "baseSkillId": primary["primarySkill"]["skillId"],
            "baseSkillVersionId": primary["primarySkill"]["skillVersionId"],
            "mutationIds": mutation_ids,
            "evolutionIds": evolution_ids,
        },
        "agent": {
            "role": "Multi-Skill financial research orchestrator",
            "objective": project_description.strip(),
            "instruction": instruction,
        },
        "primarySkill": deepcopy(primary["primarySkill"]),
        "multiSkill": {
            "strategy": "orchestrated-sequential-v1",
            "primaryRole": normalized_primary_role,
            "sourceRunIds": source_run_ids,
            "supportingSkills": supporting_skills,
            "routing": normalized_routing,
            "conflictPolicy": conflict_policy,
        },
        "workflow": workflow,
        "tools": tools,
        "rules": rules,
        "runtimeDefaults": runtime_defaults,
        "evaluationEvidence": {
            "mode": "capability-simulation-v1",
            "runtimeVerified": False,
            "sourceRunStatus": "victory",
            "objectiveScore": objective_score,
            "encountersPassed": sum(int(item["encountersPassed"]) for item in evidence_items),
            "encounterTotal": sum(int(item["encounterTotal"]) for item in evidence_items),
            "finalStats": _average_stats(sources),
            "benchmarkIds": _unique(
                [
                    *[
                        str(benchmark_id)
                        for item in evidence_items
                        for benchmark_id in item.get("benchmarkIds", [])
                    ],
                    "multi-skill-merge-contract-v1",
                ]
            ),
        },
        "limitations": [
            "Multi-Skill routing is declarative and remains runtimeVerified=false until a CaseValidation succeeds.",
            "Each source preset passed its own deterministic Evolution Run; this does not prove independent causal contribution.",
            "Native upstream Skill scripts may still require optional models, providers, and Python modules.",
            "Candidate status does not authorize automatic production deployment.",
        ],
        "digest": "pending",
    }
    normalized = AgentPreset.model_validate(payload).model_dump(mode="json")
    normalized["digest"] = agent_preset_digest(normalized)
    return AgentPreset.model_validate(normalized).model_dump(mode="json")
