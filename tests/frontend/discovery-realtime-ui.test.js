import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const read = (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("Vue Discovery 使用真实 Search Run，并把网页材料直接提炼为可编辑 Skill", async () => {
  const [controller, searchView, candidateCard, sourceTree, preview, review, api] = await Promise.all([
    read("frontend/src/composables/useDiscovery.ts"),
    read("frontend/src/components/discovery/SearchView.vue"),
    read("frontend/src/components/discovery/CandidateCard.vue"),
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
  assert.match(searchView, /提炼 Skill/);
  assert.match(searchView, /保存沉淀/);
  assert.match(candidateCard, /controller\.openCandidateDraft/);
  assert.match(candidateCard, /提炼为 Skill/);
  assert.match(sourceTree, /source\.discoveredBy/);
  assert.match(sourceTree, /artifactPath/);
  assert.match(preview, /原始快照/);
  assert.match(preview, /Skill 草稿/);
  assert.match(preview, /saveCandidateDraft/);
  assert.match(review, /confirmImport/);
  assert.match(controller, /convertMaterial/);
  assert.match(controller, /preview\.rawContent/);
  assert.match(controller, /storeSkillGenome\(draft, 'web-discovery', preview\.rawContent\)/);
  assert.match(api, /\/api\/discovery\/search-runs/);
  assert.match(api, /\/api\/discovery\/import-batches/);
});
