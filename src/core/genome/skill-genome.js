export const SKILL_GENOME_VERSION = "1.0.0";
export const SKILL_STATUSES = [
  "quarantine",
  "initial",
  "evolving",
  "candidate",
  "production",
  "retired",
];

const REQUIRED_OBJECTS = ["metadata", "prompt", "workflow", "evaluation", "provenance", "risk"];
const REQUIRED_ARRAYS = ["inputs", "outputs", "constraints", "tools", "capabilities", "testCases"];

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function addError(errors, path, message) {
  errors.push({ path, message });
}

export function validateSkillGenome(genome) {
  const errors = [];
  const warnings = [];

  if (!isObject(genome)) {
    return { valid: false, errors: [{ path: "$", message: "Skill Genome 必须是对象" }], warnings };
  }

  if (genome.schemaVersion !== SKILL_GENOME_VERSION) {
    addError(errors, "schemaVersion", `必须为 ${SKILL_GENOME_VERSION}`);
  }
  if (!/^[a-z0-9][a-z0-9._-]{2,127}$/.test(genome.id ?? "")) {
    addError(errors, "id", "必须是 3-128 位小写标识符");
  }
  if (!String(genome.name ?? "").trim()) addError(errors, "name", "不能为空");
  if (!String(genome.description ?? "").trim()) addError(errors, "description", "不能为空");
  if (!SKILL_STATUSES.includes(genome.status)) addError(errors, "status", "生命周期状态无效");

  for (const key of REQUIRED_OBJECTS) {
    if (!isObject(genome[key])) addError(errors, key, "必须是对象");
  }
  for (const key of REQUIRED_ARRAYS) {
    if (!Array.isArray(genome[key])) addError(errors, key, "必须是数组");
  }

  if (isObject(genome.metadata)) {
    if (!String(genome.metadata.category ?? "").trim()) addError(errors, "metadata.category", "不能为空");
    if (!String(genome.metadata.license ?? "").trim()) addError(errors, "metadata.license", "不能为空");
    if (!Array.isArray(genome.metadata.tags)) addError(errors, "metadata.tags", "必须是数组");
    if (
      typeof genome.metadata.completeness !== "number" ||
      genome.metadata.completeness < 0 ||
      genome.metadata.completeness > 100
    ) {
      addError(errors, "metadata.completeness", "必须在 0-100 之间");
    }
  }

  if (isObject(genome.prompt)) {
    for (const key of ["role", "objective", "instruction"]) {
      if (!String(genome.prompt[key] ?? "").trim()) addError(errors, `prompt.${key}`, "不能为空");
    }
  }

  const steps = genome.workflow?.steps;
  if (!Array.isArray(steps)) {
    addError(errors, "workflow.steps", "必须是数组");
  } else {
    const ids = new Set();
    steps.forEach((step, index) => {
      if (!isObject(step)) {
        addError(errors, `workflow.steps[${index}]`, "必须是对象");
        return;
      }
      if (!String(step.id ?? "").trim()) addError(errors, `workflow.steps[${index}].id`, "不能为空");
      if (ids.has(step.id)) addError(errors, `workflow.steps[${index}].id`, "步骤 ID 重复");
      ids.add(step.id);
      if (step.order !== index + 1) warnings.push({ path: `workflow.steps[${index}].order`, message: "建议连续排序" });
      if (!String(step.instruction ?? "").trim()) addError(errors, `workflow.steps[${index}].instruction`, "不能为空");
    });
    if (steps.length < 2) warnings.push({ path: "workflow.steps", message: "少于两个步骤，可能不足以形成可执行 Skill" });
  }

  if (Array.isArray(genome.capabilities)) {
    const capabilityIds = new Set();
    genome.capabilities.forEach((capability, index) => {
      if (!isObject(capability)) {
        addError(errors, `capabilities[${index}]`, "必须是对象");
        return;
      }
      if (!String(capability.id ?? "").trim()) addError(errors, `capabilities[${index}].id`, "不能为空");
      if (capabilityIds.has(capability.id)) addError(errors, `capabilities[${index}].id`, "能力 ID 重复");
      capabilityIds.add(capability.id);
      if (typeof capability.level !== "number" || capability.level < 0 || capability.level > 100) {
        addError(errors, `capabilities[${index}].level`, "必须在 0-100 之间");
      }
      if (!Array.isArray(capability.tags)) addError(errors, `capabilities[${index}].tags`, "必须是数组");
      if (!Array.isArray(capability.evidence)) addError(errors, `capabilities[${index}].evidence`, "必须是数组");
    });
  }

  if (isObject(genome.provenance)) {
    for (const key of ["platform", "author", "fingerprint", "capturedAt"]) {
      if (!String(genome.provenance[key] ?? "").trim()) addError(errors, `provenance.${key}`, "不能为空");
    }
  }

  if (isObject(genome.risk)) {
    if (!["low", "medium", "high"].includes(genome.risk.level)) addError(errors, "risk.level", "风险级别无效");
    if (!Array.isArray(genome.risk.reasons)) addError(errors, "risk.reasons", "必须是数组");
    if (typeof genome.risk.executableContent !== "boolean") addError(errors, "risk.executableContent", "必须是布尔值");
  }

  if (["unknown", "NOASSERTION"].includes(genome.metadata?.license)) {
    warnings.push({ path: "metadata.license", message: "许可证未知，不能进入 Initial Skill Library" });
  }
  if (genome.risk?.level === "high") {
    warnings.push({ path: "risk.level", message: "高风险候选不能进入 Initial Skill Library" });
  }

  return { valid: errors.length === 0, errors, warnings };
}

export function assertSkillGenome(genome) {
  const result = validateSkillGenome(genome);
  if (!result.valid) {
    const message = result.errors.map((error) => `${error.path}: ${error.message}`).join("; ");
    throw new Error(`Invalid Skill Genome: ${message}`);
  }
  return genome;
}

export function capabilityProfileFromGenome(genome) {
  const profile = {
    quality: 35,
    robustness: 35,
    speed: 45,
    efficiency: 45,
    security: 30,
    vision: 10,
    structure: 35,
  };

  for (const capability of genome.capabilities ?? []) {
    const stats = capability.tags ?? [];
    for (const stat of Object.keys(profile)) {
      if (capability.id === stat || stats.includes(stat)) profile[stat] = Math.max(profile[stat], capability.level);
    }
  }

  return profile;
}
