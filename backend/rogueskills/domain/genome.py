import re
from typing import Any

SKILL_GENOME_VERSION = "1.0.0"
SKILL_STATUSES = [
    "quarantine",
    "initial",
    "evolving",
    "candidate",
    "production",
    "retired",
]
REQUIRED_OBJECTS = ["metadata", "prompt", "workflow", "evaluation", "provenance", "risk"]
REQUIRED_ARRAYS = ["inputs", "outputs", "constraints", "tools", "capabilities", "testCases"]


class InvalidSkillGenome(ValueError):
    pass


def _is_object(value: object) -> bool:
    return isinstance(value, dict)


def validate_skill_genome(genome: object) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def error(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    if not _is_object(genome):
        return {
            "valid": False,
            "errors": [{"path": "$", "message": "Skill Genome 必须是对象"}],
            "warnings": warnings,
        }

    assert isinstance(genome, dict)
    if genome.get("schemaVersion") != SKILL_GENOME_VERSION:
        error("schemaVersion", f"必须为 {SKILL_GENOME_VERSION}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,127}", str(genome.get("id", ""))):
        error("id", "必须是 3-128 位小写标识符")
    if not str(genome.get("name", "")).strip():
        error("name", "不能为空")
    if not str(genome.get("description", "")).strip():
        error("description", "不能为空")
    if genome.get("status") not in SKILL_STATUSES:
        error("status", "生命周期状态无效")

    for key in REQUIRED_OBJECTS:
        if not _is_object(genome.get(key)):
            error(key, "必须是对象")
    for key in REQUIRED_ARRAYS:
        if not isinstance(genome.get(key), list):
            error(key, "必须是数组")

    metadata = genome.get("metadata")
    if isinstance(metadata, dict):
        if not str(metadata.get("category", "")).strip():
            error("metadata.category", "不能为空")
        if not str(metadata.get("license", "")).strip():
            error("metadata.license", "不能为空")
        if not isinstance(metadata.get("tags"), list):
            error("metadata.tags", "必须是数组")
        completeness = metadata.get("completeness")
        if not isinstance(completeness, (int, float)) or not 0 <= completeness <= 100:
            error("metadata.completeness", "必须在 0-100 之间")

    prompt = genome.get("prompt")
    if isinstance(prompt, dict):
        for key in ("role", "objective", "instruction"):
            if not str(prompt.get(key, "")).strip():
                error(f"prompt.{key}", "不能为空")

    workflow = genome.get("workflow")
    steps = workflow.get("steps") if isinstance(workflow, dict) else None
    if not isinstance(steps, list):
        error("workflow.steps", "必须是数组")
    else:
        step_ids: set[object] = set()
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                error(f"workflow.steps[{index}]", "必须是对象")
                continue
            if not str(step.get("id", "")).strip():
                error(f"workflow.steps[{index}].id", "不能为空")
            if step.get("id") in step_ids:
                error(f"workflow.steps[{index}].id", "步骤 ID 重复")
            step_ids.add(step.get("id"))
            if step.get("order") != index + 1:
                warnings.append(
                    {"path": f"workflow.steps[{index}].order", "message": "建议连续排序"}
                )
            if not str(step.get("instruction", "")).strip():
                error(f"workflow.steps[{index}].instruction", "不能为空")
        if len(steps) < 2:
            warnings.append(
                {"path": "workflow.steps", "message": "少于两个步骤，可能不足以形成可执行 Skill"}
            )

    capabilities = genome.get("capabilities")
    if isinstance(capabilities, list):
        capability_ids: set[object] = set()
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, dict):
                error(f"capabilities[{index}]", "必须是对象")
                continue
            if not str(capability.get("id", "")).strip():
                error(f"capabilities[{index}].id", "不能为空")
            if capability.get("id") in capability_ids:
                error(f"capabilities[{index}].id", "能力 ID 重复")
            capability_ids.add(capability.get("id"))
            level = capability.get("level")
            if not isinstance(level, (int, float)) or not 0 <= level <= 100:
                error(f"capabilities[{index}].level", "必须在 0-100 之间")
            if not isinstance(capability.get("tags"), list):
                error(f"capabilities[{index}].tags", "必须是数组")
            if not isinstance(capability.get("evidence"), list):
                error(f"capabilities[{index}].evidence", "必须是数组")

    provenance = genome.get("provenance")
    if isinstance(provenance, dict):
        for key in ("platform", "author", "fingerprint", "capturedAt"):
            if not str(provenance.get(key, "")).strip():
                error(f"provenance.{key}", "不能为空")

    risk = genome.get("risk")
    if isinstance(risk, dict):
        if risk.get("level") not in ("low", "medium", "high"):
            error("risk.level", "风险级别无效")
        if not isinstance(risk.get("reasons"), list):
            error("risk.reasons", "必须是数组")
        if not isinstance(risk.get("executableContent"), bool):
            error("risk.executableContent", "必须是布尔值")

    runtime_binding = genome.get("runtimeBinding")
    if runtime_binding is not None:
        if not isinstance(runtime_binding, dict):
            error("runtimeBinding", "必须是对象")
        else:
            if runtime_binding.get("contractVersion") != "1.0.0":
                error("runtimeBinding.contractVersion", "必须为 1.0.0")
            if runtime_binding.get("kind") != "agent-preset":
                error("runtimeBinding.kind", "必须为 agent-preset")
            for key in ("presetId", "presetDigest", "validationId"):
                if not str(runtime_binding.get(key, "")).strip():
                    error(f"runtimeBinding.{key}", "不能为空")
            if not re.fullmatch(
                r"sha256:[a-f0-9]{64}", str(runtime_binding.get("presetDigest", ""))
            ):
                error("runtimeBinding.presetDigest", "必须是有效的 SHA-256 digest")

    runtime_verification = genome.get("runtimeVerification")
    if runtime_verification is not None:
        if not isinstance(runtime_verification, dict):
            error("runtimeVerification", "必须是对象")
        else:
            if runtime_verification.get("runtimeVerified") is not True:
                error("runtimeVerification.runtimeVerified", "必须为 true")
            for key in (
                "casePackId",
                "casePackVersion",
                "caseId",
                "evaluationId",
                "verifiedAt",
            ):
                if not str(runtime_verification.get(key, "")).strip():
                    error(f"runtimeVerification.{key}", "不能为空")
            for key in ("sourceDigest", "datasetDigest"):
                value = runtime_verification.get(key)
                if value is not None and not re.fullmatch(r"sha256:[a-f0-9]{64}", str(value)):
                    error(f"runtimeVerification.{key}", "必须是有效的 SHA-256 digest")

    if isinstance(metadata, dict) and metadata.get("license") in ("unknown", "NOASSERTION"):
        warnings.append(
            {"path": "metadata.license", "message": "许可证未知，不能进入 Initial Skill Library"}
        )
    if isinstance(risk, dict) and risk.get("level") == "high":
        warnings.append(
            {"path": "risk.level", "message": "高风险候选不能进入 Initial Skill Library"}
        )

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def assert_skill_genome(genome: dict[str, Any]) -> dict[str, Any]:
    result = validate_skill_genome(genome)
    if not result["valid"]:
        message = "; ".join(f"{item['path']}: {item['message']}" for item in result["errors"])
        raise InvalidSkillGenome(f"Invalid Skill Genome: {message}")
    return genome


def capability_profile_from_genome(genome: dict[str, Any]) -> dict[str, float]:
    profile: dict[str, float] = {
        "quality": 35,
        "robustness": 35,
        "speed": 45,
        "efficiency": 45,
        "security": 30,
        "vision": 10,
        "structure": 35,
    }
    for capability in genome.get("capabilities", []):
        tags = capability.get("tags", [])
        for stat in profile:
            if capability.get("id") == stat or stat in tags:
                profile[stat] = max(profile[stat], capability.get("level", 0))
    return profile
