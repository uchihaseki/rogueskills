// Frozen JS parity oracle. Do not import from the browser or production backend.
import { clamp, round } from "../shared/random.js";
import { validateSkillGenome } from "../genome/skill-genome.js";

export const ADMISSION_BENCHMARK_ID = "library-admission-v1";
export const SCENARIO_BENCHMARK_ID = "scenario-runtime-v1";

function weightedAverage(items) {
  const totalWeight = items.reduce((total, item) => total + item.weight, 0);
  return items.reduce((total, item) => total + item.score * item.weight, 0) / Math.max(1, totalWeight);
}

function admissionCase({ id, label, weight, score, hardGate = false, message }) {
  return {
    id,
    label,
    weight,
    score: round(clamp(score, 0, 100), 1),
    passed: score >= 70,
    hardGate,
    message,
  };
}

export function runAdmissionBenchmark(genome) {
  const schema = validateSkillGenome(genome);
  const provenanceFields = ["platform", "author", "fingerprint", "capturedAt"];
  const provenanceCoverage = provenanceFields.filter((field) => genome.provenance?.[field]).length / provenanceFields.length;
  const workflowScore = clamp((genome.workflow?.steps?.length ?? 0) * 24, 0, 100);
  const constraintScore = clamp((genome.constraints?.length ?? 0) * 34, 0, 100);
  const testScore = clamp((genome.testCases?.length ?? 0) * 34, 0, 100);
  const evidenceCount = (genome.capabilities ?? []).filter((capability) => capability.evidence?.length).length;
  const capabilityScore = clamp((evidenceCount / Math.max(1, genome.capabilities?.length ?? 0)) * 100, 0, 100);
  const licensePassed = !["unknown", "NOASSERTION", ""].includes(genome.metadata?.license ?? "unknown");
  const safetyPassed = genome.risk?.level !== "high";

  const cases = [
    admissionCase({
      id: "schema",
      label: "Skill Genome Schema",
      weight: 25,
      score: schema.valid ? 100 : 0,
      hardGate: true,
      message: schema.valid ? "符合 Skill Genome 1.0" : schema.errors.map((error) => error.path).join(", "),
    }),
    admissionCase({
      id: "provenance",
      label: "Source Provenance",
      weight: 12,
      score: provenanceCoverage * 100,
      message: `${Math.round(provenanceCoverage * 100)}% 来源字段完整`,
    }),
    admissionCase({
      id: "workflow",
      label: "Executable Workflow",
      weight: 15,
      score: workflowScore,
      message: `${genome.workflow?.steps?.length ?? 0} 个可执行步骤`,
    }),
    admissionCase({
      id: "constraints",
      label: "Constraints & Safety Rules",
      weight: 10,
      score: constraintScore,
      message: `${genome.constraints?.length ?? 0} 条明确约束`,
    }),
    admissionCase({
      id: "test-cases",
      label: "Declared Test Cases",
      weight: 10,
      score: testScore,
      message: `${genome.testCases?.length ?? 0} 个测试草案`,
    }),
    admissionCase({
      id: "license",
      label: "License Policy",
      weight: 10,
      score: licensePassed ? 100 : 0,
      hardGate: true,
      message: licensePassed ? `许可证：${genome.metadata.license}` : "许可证未知",
    }),
    admissionCase({
      id: "static-safety",
      label: "Static Safety",
      weight: 13,
      score: safetyPassed ? (genome.risk.level === "low" ? 100 : 75) : 0,
      hardGate: true,
      message: safetyPassed ? `风险级别：${genome.risk.level}` : genome.risk.reasons.join("; "),
    }),
    admissionCase({
      id: "capability-evidence",
      label: "Capability Evidence",
      weight: 5,
      score: capabilityScore,
      message: `${evidenceCount}/${genome.capabilities?.length ?? 0} 个能力包含证据`,
    }),
  ];
  const score = round(weightedAverage(cases), 1);
  const hardGatesPassed = cases.filter((item) => item.hardGate).every((item) => item.passed);
  const passed = score >= 75 && hardGatesPassed;

  return {
    runId: `admission-${genome.id}-${Date.now().toString(36)}`,
    benchmarkId: ADMISSION_BENCHMARK_ID,
    split: "validation",
    score,
    passed,
    hardGatesPassed,
    cases,
    summary: passed
      ? "候选通过 Initial Skill Library 准入评测"
      : "候选未满足准入分数或硬门槛",
  };
}

function profileScore(profile, weights) {
  return Object.entries(weights).reduce(
    (total, [stat, weight]) => total + (profile[stat] ?? 0) * weight,
    0,
  );
}

function scenarioCase(id, label, observed, required, weight, details) {
  const margin = observed - required;
  const score = clamp(70 + margin * 2.15, 0, 100);
  return {
    id,
    label,
    observed: round(observed, 1),
    required: round(required, 1),
    margin: round(margin, 1),
    weight,
    score: round(score, 1),
    passed: score >= 70,
    details,
  };
}

export function runScenarioBenchmark({
  profile,
  scenario,
  difficulty,
  nodeType = "normal",
  computeAvailable = 100,
  objectiveScore = 0,
}) {
  const primaryCapability = profileScore(profile, scenario.requirements);
  const recoveryCapability = primaryCapability * 0.72 + (profile.robustness ?? 0) * 0.28;
  const budgetCapability =
    (profile.efficiency ?? 0) * 0.5 + (profile.speed ?? 0) * 0.3 + (profile.quality ?? 0) * 0.2;
  const outputCapability =
    (profile.structure ?? 0) * 0.45 + (profile.quality ?? 0) * 0.35 + (profile.robustness ?? 0) * 0.2;
  const securityRequired = scenario.securityFloor ?? Math.max(30, difficulty - 12);
  const securityCapability = profile.security ?? 0;
  const typePressure = nodeType === "boss" ? 3 : nodeType === "elite" ? 1.5 : 0;

  const cases = [
    scenarioCase(
      "nominal",
      "Nominal business case",
      primaryCapability,
      difficulty - 5,
      24,
      "核心业务能力",
    ),
    scenarioCase(
      "standard",
      "Standard acceptance case",
      primaryCapability,
      difficulty + typePressure,
      24,
      "标准验收条件",
    ),
    scenarioCase(
      "degraded",
      "Degraded environment",
      recoveryCapability,
      difficulty + 2 + typePressure,
      20,
      "工具失效或输入分布变化",
    ),
    scenarioCase(
      "budget-sla",
      "Cost and latency SLA",
      budgetCapability,
      difficulty - 4 + typePressure,
      16,
      "成本与延迟约束",
    ),
    scenarioCase(
      "output-contract",
      "Output contract",
      outputCapability,
      difficulty - 3 + typePressure,
      10,
      "结构化输出与完整性",
    ),
    scenarioCase(
      "security-boundary",
      "Security boundary",
      securityCapability,
      securityRequired,
      6,
      "指令隔离与最小权限",
    ),
  ];

  const threshold = nodeType === "boss" ? 78 : nodeType === "elite" ? 74 : 70;
  const coverage = round(weightedAverage(cases), 1);
  const securityGatePassed = !scenario.securityFloor || securityCapability >= scenario.securityFloor;
  const passed = coverage >= threshold && securityGatePassed;
  const latency = round(
    Math.max(1.2, 15 - (profile.speed ?? 0) * 0.12 + difficulty * 0.04 + typePressure * 0.35),
    1,
  );
  const computeCost = Math.max(
    3,
    Math.round(
      (96 - (profile.efficiency ?? 0)) * 0.12 +
        difficulty * 0.045 +
        (nodeType === "elite" ? 2 : nodeType === "boss" ? 4 : 0),
    ),
  );
  const budgetExceeded = computeCost > computeAvailable;
  const deficit = Math.max(0, threshold - coverage);
  let stabilityDamage = passed ? 0 : Math.max(1, Math.ceil(deficit / 12));
  if (!securityGatePassed) stabilityDamage += 2;
  if (budgetExceeded) stabilityDamage += 1;
  const computeReward = passed
    ? nodeType === "boss"
      ? 18
      : nodeType === "elite"
        ? 13
        : 8
    : 2;

  return {
    benchmarkId: SCENARIO_BENCHMARK_ID,
    passed,
    threshold,
    coverage,
    quality: round(
      clamp(
        (profile.quality ?? 0) * 0.62 +
          (profile.structure ?? 0) * 0.2 +
          (profile.robustness ?? 0) * 0.18,
        0,
        100,
      ),
      1,
    ),
    latency,
    capability: round(primaryCapability, 2),
    difficulty,
    computeCost,
    computeReward,
    stabilityDamage,
    securityGatePassed,
    budgetExceeded,
    objectiveScore,
    cases,
  };
}
