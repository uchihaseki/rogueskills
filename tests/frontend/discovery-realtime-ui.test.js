import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("Vue Discovery 使用真实 Search Run 事件并提供来源展开、预览和批量确认", async () => {
  const [controller, searchView, sourceTree, preview, review, api] = await Promise.all([
    read("frontend/src/composables/useDiscovery.ts"),
    read("frontend/src/components/discovery/SearchView.vue"),
    read("frontend/src/components/discovery/SourceTree.vue"),
    read("frontend/src/components/discovery/CandidatePreviewDrawer.vue"),
    read("frontend/src/components/discovery/ImportReviewDialog.vue"),
    read("frontend/src/api/client.ts"),
  ]);

  assert.match(controller, /new EventSource\(discoveryEventsUrl/);
  assert.match(controller, /run\.review_ready/);
  assert.match(controller, /selectedIds/);
  assert.match(searchView, /SearchProgressPanel/);
  assert.match(searchView, /SourceTree/);
  assert.match(searchView, /复核并保存/);
  assert.match(sourceTree, /source\.discoveredBy/);
  assert.match(sourceTree, /artifactPath/);
  assert.match(preview, /原始快照/);
  assert.match(preview, /Genome Draft/);
  assert.match(review, /confirmImport/);
  assert.match(api, /\/api\/discovery\/search-runs/);
  assert.match(api, /\/api\/discovery\/import-batches/);
});
