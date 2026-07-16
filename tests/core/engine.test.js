import test from "node:test";
import assert from "node:assert/strict";

import {
  chooseMutation,
  createRun,
  evaluateEncounter,
  generateMap,
  getCurrentLayer,
  resolveCurrentNode,
  selectNode,
} from "../../legacy/src/core/evolution/engine.js";

test("相同 Seed 生成完全相同的地图", () => {
  assert.deepEqual(generateMap("DAILY-0714"), generateMap("DAILY-0714"));
});

test("不同 Seed 会改变至少一个普通节点", () => {
  const first = JSON.stringify(generateMap("SEED-A"));
  const second = JSON.stringify(generateMap("SEED-B"));
  assert.notEqual(first, second);
});

test("同一构筑对同一节点的评估可复现", () => {
  const run = createRun({ seed: "REPLAY-001" });
  const node = getCurrentLayer(run)[0];
  const selected = selectNode(run, node.id);

  assert.deepEqual(evaluateEncounter(selected), evaluateEncounter(selected));
});

test("Mutation 会修改属性和复杂度", () => {
  const run = createRun({ seed: "MUTATION-001" });
  const rewardState = {
    ...run,
    phase: "reward",
    currentDraft: ["schema_validator"],
  };
  const next = chooseMutation(rewardState, "schema_validator");

  assert.equal(next.stats.structure, run.stats.structure + 15);
  assert.equal(next.complexityUsed, 1);
  assert.deepEqual(next.mutationIds, ["schema_validator"]);
});

test("满足标签配方后触发武器进化且只触发一次", () => {
  let run = createRun({ seed: "EVOLVE-001" });

  for (const mutationId of ["screenshot_ocr", "semantic_locator", "schema_validator"]) {
    run = chooseMutation(
      { ...run, phase: "reward", currentDraft: [mutationId] },
      mutationId,
    );
  }

  assert.ok(run.evolutionIds.includes("adaptive_web_extractor"));
  assert.equal(
    run.evolutionIds.filter((id) => id === "adaptive_web_extractor").length,
    1,
  );
});

test("高能力构筑可连续通过三幕 Boss 并获得候选资格", () => {
  let run = createRun({ seed: "BOSS-FLOW-001" });
  run = {
    ...run,
    stats: Object.fromEntries(Object.keys(run.stats).map((stat) => [stat, 100])),
  };

  for (let actIndex = 0; actIndex < 3; actIndex += 1) {
    run = { ...run, layerIndex: 3, phase: "choose_node" };
    const boss = getCurrentLayer(run)[0];
    run = selectNode(run, boss.id);
    run = resolveCurrentNode(run);
  }

  assert.equal(run.status, "victory");
  assert.equal(run.phase, "ended");
});
