from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from rogueskills.contracts.presets import AgentPreset

from .catalogs import PRESET_CONTRIBUTIONS, RUN_MODES
from .genome import validate_skill_genome
from .shared import round_number


class InvalidAgentPreset(ValueError):
    pass


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def agent_preset_digest(preset: dict[str, Any]) -> str:
    content = deepcopy(preset)
    content.pop("digest", None)
    return _digest(content)


def _objective_score(state: dict[str, Any]) -> float:
    weights = RUN_MODES[state["modeId"]]["weights"]
    return round_number(
        sum(state["stats"].get(stat, 0) * weight for stat, weight in weights.items()), 1
    )


def compile_agent_preset(
    *,
    run: dict[str, Any],
    run_revision: int,
    base_skill_version_id: str,
    base_skill_genome: dict[str, Any],
    project_name: str,
    project_description: str,
    scenario: str,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    if run.get("status") != "victory" or run.get("phase") != "ended":
        raise InvalidAgentPreset("Only a completed victory Run can produce an AgentPreset.")
    validation = validate_skill_genome(base_skill_genome)
    if not validation["valid"]:
        raise InvalidAgentPreset("The Run base Skill Genome is invalid.")
    if base_skill_genome.get("risk", {}).get("level") == "high":
        raise InvalidAgentPreset("A high-risk Skill cannot produce an AgentPreset.")

    instructions: list[str] = []
    constraints = list(base_skill_genome.get("constraints", []))
    retry_rules: list[str] = []
    fallback_rules: list[str] = []
    output_rules: list[str] = []
    tools = list(base_skill_genome.get("tools", []))
    workflow: list[dict[str, Any]] = []

    for index, step in enumerate(base_skill_genome.get("workflow", {}).get("steps", [])):
        workflow.append(
            {
                "id": str(step.get("id") or f"base-step-{index + 1}"),
                "order": index + 1,
                "instruction": str(step.get("instruction", "")).strip(),
                "tool": step.get("tool"),
                "source": "base-skill",
            }
        )

    runtime_overrides: dict[str, Any] = {}

    def collect(contribution: dict[str, Any], source: str) -> None:
        instructions.extend(contribution.get("instructions", []))
        constraints.extend(contribution.get("constraints", []))
        retry_rules.extend(contribution.get("retryRules", []))
        fallback_rules.extend(contribution.get("fallbackRules", []))
        output_rules.extend(contribution.get("outputValidationRules", []))
        tools.extend(contribution.get("tools", []))
        runtime_overrides.update(contribution.get("runtime", {}))
        for step in contribution.get("workflowSteps", []):
            instruction = " ".join(str(step.get("instruction", "")).split()).strip()
            if not instruction or any(item["instruction"] == instruction for item in workflow):
                continue
            workflow.append(
                {
                    "id": f"preset-step-{len(workflow) + 1}",
                    "order": len(workflow) + 1,
                    "instruction": instruction,
                    "tool": step.get("tool"),
                    "source": source,
                }
            )

    for mutation_id in run.get("mutationIds", []):
        collect(PRESET_CONTRIBUTIONS["mutations"].get(mutation_id, {}), f"mutation:{mutation_id}")
    for evolution_id in run.get("evolutionIds", []):
        collect(
            PRESET_CONTRIBUTIONS["evolutions"].get(evolution_id, {}),
            f"evolution:{evolution_id}",
        )

    instruction = base_skill_genome["prompt"]["instruction"].strip()
    additions = _unique(instructions)
    if additions:
        instruction = f"{instruction}\n\nRuntime configuration additions:\n" + "\n".join(
            f"- {item}" for item in additions
        )

    mode_defaults = deepcopy(PRESET_CONTRIBUTIONS["modes"].get(run["modeId"], {}))
    mode_defaults.update(runtime_overrides)
    mode_defaults.setdefault("enforceBudget", True)
    history = run.get("encounterHistory", [])
    benchmark_ids = _unique(
        [str(item.get("benchmarkId", "")) for item in history if item.get("benchmarkId")]
    )
    timestamp = (clock or (lambda: datetime.now(UTC)))().isoformat().replace("+00:00", "Z")
    preset_id = f"preset-{hashlib.sha256(run['id'].encode('utf-8')).hexdigest()[:20]}"
    real_evidence = run.get("runtimeVerification")
    if real_evidence:
        evaluation_evidence = {
            "mode": "real-finance-case-v1",
            "runtimeVerified": bool(real_evidence.get("runtimeVerified")),
            "sourceRunStatus": "victory",
            "objectiveScore": float(real_evidence.get("score", 0)),
            "encountersPassed": 1 if real_evidence.get("runtimeVerified") else 0,
            "encounterTotal": 1,
            "finalStats": deepcopy(run.get("stats", {})),
            "benchmarkIds": [str(real_evidence.get("benchmarkId", "finance-real-case-v1"))],
        }
        limitations = [
            "This preset contains one primary Skill and does not provide multi-Skill routing.",
            "The runtime evidence comes from the persisted public-data Finance Case trace.",
            "Candidate status does not authorize automatic production deployment.",
        ]
    else:
        evaluation_evidence = {
            "mode": "capability-simulation-v1",
            "runtimeVerified": False,
            "sourceRunStatus": "victory",
            "objectiveScore": _objective_score(run),
            "encountersPassed": sum(bool(item.get("passed")) for item in history),
            "encounterTotal": len(history),
            "finalStats": deepcopy(run["stats"]),
            "benchmarkIds": benchmark_ids,
        }
        limitations = [
            "This preset contains one primary Skill and does not provide multi-Skill routing.",
            "Its evidence comes from the deterministic capability simulation, not a real tool Runtime.",
            "Candidate status does not authorize automatic production deployment.",
        ]
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
            "runId": run["id"],
            "runRevision": run_revision,
            "seed": run["seed"],
            "modeId": run["modeId"],
            "baseSkillId": run["baseSkillId"],
            "baseSkillVersionId": base_skill_version_id,
            "mutationIds": list(run.get("mutationIds", [])),
            "evolutionIds": list(run.get("evolutionIds", [])),
        },
        "agent": {
            "role": base_skill_genome["prompt"]["role"],
            "objective": base_skill_genome["prompt"]["objective"],
            "instruction": instruction,
        },
        "primarySkill": {
            "role": "primary",
            "skillId": run["baseSkillId"],
            "skillVersionId": base_skill_version_id,
            "genome": deepcopy(base_skill_genome),
        },
        "workflow": workflow,
        "tools": _unique(tools),
        "rules": {
            "constraints": _unique(constraints),
            "retry": _unique(retry_rules),
            "fallback": _unique(fallback_rules),
            "outputValidation": _unique(output_rules),
        },
        "runtimeDefaults": mode_defaults,
        "evaluationEvidence": evaluation_evidence,
        "limitations": limitations,
    }
    payload["digest"] = "pending"
    normalized = AgentPreset.model_validate(payload).model_dump(mode="json")
    normalized["digest"] = agent_preset_digest(normalized)
    return AgentPreset.model_validate(normalized).model_dump(mode="json")
