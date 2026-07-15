import test from "node:test";
import assert from "node:assert/strict";

import { createApiRouter } from "../../src/backend/api/router.mjs";
import { SkillRepository } from "../../src/backend/repository/skill-repository.mjs";
import { INITIAL_BROWSER_SKILL } from "../../src/core/genome/seed-skills.js";

test("Search Gateway 提供健康检查和 Initial Library", async () => {
  const repository = new SkillRepository(":memory:");
  repository.upsertSkill(INITIAL_BROWSER_SKILL, { sourceId: "seed" });
  const route = createApiRouter({ repository });

  const health = await route({ method: "GET", url: "/api/health" });
  const library = await route({ method: "GET", url: "/api/library/initial" });

  assert.equal(health.status, 200);
  assert.equal(library.body.skills.length, 1);
  assert.equal(library.body.skills[0].id, INITIAL_BROWSER_SKILL.id);
  repository.close();
});

test("候选可通过 API 完成转换、持久化、Benchmark 和准入", async () => {
  const repository = new SkillRepository(":memory:");
  const route = createApiRouter({ repository });

  const converted = await route({
    method: "POST",
    url: "/api/materials/convert",
    body: {
      title: "Refund Review SOP",
      license: "internal",
      source: { platform: "Operations Wiki", author: "Ops" },
      content: `# Refund Review\n\n## Goal\nReview refunds safely.\n\n## Steps\n1. Verify order.\n2. Check policy.\n3. Record result.\n\n## Constraints\n- Never expose payment credentials.`,
    },
  });
  assert.equal(converted.body.validation.valid, true);

  const stored = await route({
    method: "POST",
    url: "/api/skills",
    body: { genome: converted.body.genome, sourceId: "manual" },
  });
  const skillId = stored.body.skill.id;
  assert.equal(stored.status, 201);

  const benchmark = await route({ method: "POST", url: `/api/skills/${skillId}/benchmark`, body: {} });
  assert.equal(benchmark.status, 200);
  assert.equal(benchmark.body.result.passed, true);

  const promoted = await route({
    method: "POST",
    url: `/api/skills/${skillId}/promote`,
    body: { evaluationId: benchmark.body.evaluation.id },
  });
  assert.equal(promoted.body.skill.status, "initial");
  assert.equal((await route({ method: "GET", url: "/api/library/initial" })).body.skills.length, 1);
  repository.close();
});

test("Search Gateway 可以搜索内置索引且缓存结果", async () => {
  const repository = new SkillRepository(":memory:");
  const route = createApiRouter({ repository, cacheTtlMs: 10_000 });
  const request = {
    method: "POST",
    url: "/api/discovery/search",
    body: { query: "browser extraction", sourceIds: ["builtin"] },
  };
  const first = await route(request);
  const second = await route(request);

  assert.ok(first.body.results.length > 0);
  assert.equal(first.body.cached, false);
  assert.equal(second.body.cached, true);
  repository.close();
});
