import test from "node:test";
import assert from "node:assert/strict";

import * as catalog from "../../legacy/src/core/evolution/catalog.js";
import {
  createRun,
  resolveCurrentNode,
  selectNode,
} from "../../legacy/src/core/evolution/engine.js";
import { INITIAL_BROWSER_SKILL } from "../../legacy/src/core/genome/seed-skills.js";
import { capabilityProfileFromGenome } from "../../legacy/src/core/genome/skill-genome.js";

test("界面可以从设置页进入首场遭遇并显示 Mutation Draft", async () => {
  const listeners = {};
  const root = {
    innerHTML: "",
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
  };
  const localData = new Map();
  let serverRun = null;
  let revision = 0;

  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  globalThis.fetch = async (path, options = {}) => {
    if (path === "/api/evolution/catalog") {
      return json({
        archetypes: catalog.ARCHETYPES,
        evolutions: catalog.EVOLUTIONS,
        monsters: catalog.MONSTERS,
        mutations: catalog.MUTATIONS,
        nodeTypes: catalog.NODE_TYPES,
        runModes: catalog.RUN_MODES,
        statLabels: catalog.STAT_LABELS,
      });
    }
    if (path === "/api/library/initial") {
      return json({
        skills: [
          {
            id: INITIAL_BROWSER_SKILL.id,
            status: "initial",
            currentVersionId: `${INITIAL_BROWSER_SKILL.id}@1`,
            genome: INITIAL_BROWSER_SKILL,
            versions: [{ id: `${INITIAL_BROWSER_SKILL.id}@1`, version: 1 }],
            capabilityProfile: capabilityProfileFromGenome(INITIAL_BROWSER_SKILL),
          },
        ],
      });
    }
    if (path === "/api/runs" && options.method === "POST") {
      const payload = JSON.parse(options.body);
      serverRun = createRun({ seed: payload.seed, modeId: payload.modeId, skillGenome: INITIAL_BROWSER_SKILL });
      revision = 1;
      return json({ run: serverRun, revision, baseSkillVersionId: `${INITIAL_BROWSER_SKILL.id}@1` }, 201);
    }
    if (path.endsWith("/select-node")) {
      serverRun = selectNode(serverRun, JSON.parse(options.body).nodeId);
      revision += 1;
      return json({ run: serverRun, revision, baseSkillVersionId: `${INITIAL_BROWSER_SKILL.id}@1` });
    }
    if (path.endsWith("/resolve")) {
      serverRun = resolveCurrentNode(serverRun);
      revision += 1;
      return json({ run: serverRun, revision, baseSkillVersionId: `${INITIAL_BROWSER_SKILL.id}@1` });
    }
    return json({ error: { code: "NOT_FOUND", message: String(path) } }, 404);
  };
  globalThis.window = { alert() {} };

  globalThis.localStorage = {
    getItem(key) {
      return localData.get(key) ?? null;
    },
    setItem(key, value) {
      localData.set(key, value);
    },
  };
  globalThis.document = {
    title: "",
    querySelector(selector) {
      if (selector === "#app") return root;
      if (selector === "#run-seed") return { value: "UI-SMOKE-001" };
      if (selector === 'input[name="mode"]:checked') return { value: "stable" };
      return null;
    },
  };

  await import("../../src/frontend/app.js?smoke-test");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(root.innerHTML, /生成 Evolution Run/);

  const click = (dataset) =>
    listeners.click({
      target: {
        closest() {
          return { dataset };
        },
      },
    });

  await click({ action: "start-run" });
  assert.match(root.innerHTML, /静态平原/);

  const nodeId = root.innerHTML.match(/data-node-id="([^"]+)"/)?.[1];
  assert.ok(nodeId);

  await click({ action: "select-node", nodeId });
  assert.match(root.innerHTML, /运行 Benchmark/);

  await click({ action: "resolve-node" });
  assert.match(root.innerHTML, /选择一个 Mutation/);
  assert.match(root.innerHTML, /BUSINESS COVERAGE/);
});
