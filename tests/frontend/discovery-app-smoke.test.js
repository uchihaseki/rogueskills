import test from "node:test";
import assert from "node:assert/strict";

test("Discovery 工作台可以搜索种子索引并把 SOP 保存到隔离库", async () => {
  const listeners = {};
  const root = {
    innerHTML: "",
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
  };
  const localData = new Map();
  const fields = {
    "#material-title": { value: "退款审核 SOP" },
    "#material-source": { value: "Operations Wiki" },
    "#material-license": { value: "internal" },
    "#material-content": {
      value: "# 退款审核\n\n## 目标\n安全处理退款。\n\n## 步骤\n1. 验证订单。\n2. 检查资格。\n3. 创建退款。\n\n## 约束\n- 必须使用原支付渠道。",
    },
  };

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
      if (selector === "#discovery-app") return root;
      return fields[selector] ?? null;
    },
  };

  await import("../../src/frontend/discovery-app.js?smoke-test");
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(root.innerHTML, /Resilient Browser Extraction/);

  const click = async (dataset) =>
    listeners.click({
      target: {
        closest() {
          return { dataset };
        },
      },
    });

  await click({ action: "switch-view", view: "convert" });
  assert.match(root.innerHTML, /SOP → SKILL GENOME/);

  await click({ action: "convert-material" });
  assert.match(root.innerHTML, /WORKFLOW · 3 STEPS/);
  assert.match(root.innerHTML, /QUARANTINE/);

  await click({ action: "stage-preview" });
  const saved = JSON.parse(localData.get("rogueskills.discovery.library.v1"));
  assert.equal(saved.length, 1);
  assert.equal(saved[0].status, "quarantine");
});
