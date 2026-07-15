import test from "node:test";
import assert from "node:assert/strict";

import { convertMaterialToSkill } from "../src/discovery-engine.js";
import { SkillRepository } from "../src/server/skill-repository.mjs";
import { INITIAL_BROWSER_SKILL } from "../src/server/seed-skills.mjs";

test("Repository 保存 Initial Skill、版本和来源快照", () => {
  const repository = new SkillRepository(":memory:");
  const stored = repository.upsertSkill(INITIAL_BROWSER_SKILL, { sourceId: "seed" });

  assert.equal(stored.status, "initial");
  assert.equal(stored.versions.length, 1);
  assert.equal(stored.snapshots.length, 1);
  assert.equal(repository.listInitialSkills().length, 1);
  repository.close();
});

test("候选必须通过准入 Benchmark 才能进入 Initial Library", () => {
  const repository = new SkillRepository(":memory:");
  const candidate = convertMaterialToSkill({
    title: "Refund Review",
    license: "internal",
    content: `# Refund Review\n\n## Goal\nReview refund requests safely.\n\n## Steps\n1. Verify the order.\n2. Check policy.\n3. Record the decision.\n\n## Constraints\n- Never expose payment credentials.`,
  });
  const stored = repository.upsertSkill(candidate, { sourceId: "manual" });

  assert.throws(() => repository.promoteToInitial(stored.id, "missing"));

  const evaluation = repository.recordEvaluation(stored.id, "library-admission-v1", "validation", {
    runId: "admission-refund-v1",
    score: 86,
    passed: true,
    cases: [],
  });
  const promoted = repository.promoteToInitial(stored.id, evaluation.id);

  assert.equal(promoted.status, "initial");
  assert.equal(promoted.versions.length, 2);
  assert.equal(promoted.genome.evaluation.lastRunId, evaluation.id);
  repository.close();
});
