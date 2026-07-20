from typing import Any

from rogueskills.contracts.presets import AgentPreset, LoadedAgentConfig
from rogueskills.domain.presets import agent_preset_digest


class AgentPresetIntegrityError(ValueError):
    pass


def load_agent_preset(preset: dict[str, Any]) -> dict[str, Any]:
    validated = AgentPreset.model_validate(preset).model_dump(mode="json")
    if agent_preset_digest(validated) != validated["digest"]:
        raise AgentPresetIntegrityError("AgentPreset digest verification failed.")

    rules = validated["rules"]
    workflow_lines = [
        f"{step['order']}. {step['instruction']}" for step in validated["workflow"]
    ]
    constraint_lines = [f"- {item}" for item in rules["constraints"]]
    developer_sections = [validated["agent"]["instruction"]]
    if workflow_lines:
        developer_sections.append("Workflow:\n" + "\n".join(workflow_lines))
    if constraint_lines:
        developer_sections.append("Constraints:\n" + "\n".join(constraint_lines))
    for label, key in (
        ("Retry rules", "retry"),
        ("Fallback rules", "fallback"),
        ("Output validation", "outputValidation"),
    ):
        if rules[key]:
            developer_sections.append(f"{label}:\n" + "\n".join(f"- {item}" for item in rules[key]))

    loaded = {
        "contractVersion": "0.1.0",
        "presetId": validated["id"],
        "presetDigest": validated["digest"],
        "project": validated["project"],
        "primarySkillVersionId": validated["primarySkill"]["skillVersionId"],
        "systemPrompt": (
            f"{validated['agent']['role']}\n\nObjective: {validated['agent']['objective']}"
        ),
        "developerPrompt": "\n\n".join(developer_sections),
        "workflow": validated["workflow"],
        "tools": validated["tools"],
        "rules": rules,
        "runtimeDefaults": validated["runtimeDefaults"],
        "runtimeVerified": False,
    }
    return LoadedAgentConfig.model_validate(loaded).model_dump(mode="json")
