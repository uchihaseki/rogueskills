import test from "node:test";
import assert from "node:assert/strict";

test("界面可以从设置页进入首场遭遇并显示 Mutation Draft", async () => {
  const listeners = {};
  const root = {
    innerHTML: "",
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
  };
  const localData = new Map();

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

  await import("../src/app.js?smoke-test");
  assert.match(root.innerHTML, /生成 Evolution Run/);

  const click = (dataset) =>
    listeners.click({
      target: {
        closest() {
          return { dataset };
        },
      },
    });

  click({ action: "start-run" });
  assert.match(root.innerHTML, /静态平原/);

  const nodeId = root.innerHTML.match(/data-node-id="([^"]+)"/)?.[1];
  assert.ok(nodeId);

  click({ action: "select-node", nodeId });
  assert.match(root.innerHTML, /运行 Benchmark/);

  click({ action: "resolve-node" });
  assert.match(root.innerHTML, /选择一个 Mutation/);
  assert.match(root.innerHTML, /BUSINESS COVERAGE/);
});
