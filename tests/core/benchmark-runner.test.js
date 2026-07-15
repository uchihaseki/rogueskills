import test from "node:test";
import assert from "node:assert/strict";

import { runAdmissionBenchmark, runScenarioBenchmark } from "../../src/core/benchmark/runner.js";
import { convertMaterialToSkill } from "../../src/core/discovery/engine.js";
import { INITIAL_BROWSER_SKILL } from "../../src/core/genome/seed-skills.js";

test("Initial Browser Skill 通过真实准入 Benchmark", () => {
  const result = runAdmissionBenchmark(INITIAL_BROWSER_SKILL);
  assert.equal(result.passed, true);
  assert.equal(result.hardGatesPassed, true);
  assert.equal(result.cases.length, 8);
});

test("未知许可证触发准入硬门槛失败", () => {
  const genome = convertMaterialToSkill({
    title: "Unknown License SOP",
    content: "# SOP\n\n## Steps\n1. Do one.\n2. Do two.\n\n## Constraints\n- Never leak secrets.",
  });
  const result = runAdmissionBenchmark(genome);
  const license = result.cases.find((item) => item.id === "license");

  assert.equal(license.passed, false);
  assert.equal(result.passed, false);
});

test("场景 Benchmark 执行六个可解释用例且不包含随机值", () => {
  const input = {
    profile: { quality: 70, robustness: 68, speed: 62, efficiency: 60, security: 55, vision: 40, structure: 72 },
    scenario: {
      id: "schema-drift",
      requirements: { quality: 0.3, robustness: 0.35, structure: 0.35 },
      severity: 2,
    },
    difficulty: 54,
    nodeType: "elite",
    computeAvailable: 80,
    objectiveScore: 65,
  };
  const first = runScenarioBenchmark(input);
  const second = runScenarioBenchmark(input);

  assert.deepEqual(first, second);
  assert.equal(first.cases.length, 6);
  assert.ok(first.coverage > 0);
});
