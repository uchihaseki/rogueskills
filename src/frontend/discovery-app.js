import { SOURCE_CONNECTORS } from "../core/discovery/catalog.js";
import {
  candidateToSkillGenome,
  connectorById,
  convertMaterialToSkill,
  parseSearchQuery,
  searchLocalIndex,
} from "../core/discovery/engine.js";
import {
  apiHealth,
  benchmarkSkill,
  deleteSkill,
  importDiscoveryCandidate,
  listSkills,
  promoteSkill,
  searchDiscovery,
  storeSkillGenome,
} from "./api-client.js";

const STORAGE_KEY = "rogueskills.discovery.library.v1";
const root = document.querySelector("#discovery-app");

const state = {
  view: "search",
  query: "browser extraction",
  sourceIds: new Set(["builtin"]),
  kindFilter: "all",
  results: [],
  providerStatus: [],
  searching: false,
  stagingId: null,
  library: loadLibrary(),
  preview: null,
  uploadedText: "",
  uploadedName: "",
  notice: null,
  gateway: "checking",
};

function localFallbackSearch(query, sourceIds) {
  const includesBuiltin = sourceIds.includes("builtin");
  const results = includesBuiltin ? searchLocalIndex(query) : [];
  const status = sourceIds.map((sourceId) =>
    sourceId === "builtin"
      ? { sourceId, state: "ok", count: results.length }
      : { sourceId, state: "unavailable", count: 0, message: "服务端不可用" },
  );
  return { results, status };
}

function loadLibrary() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveLibrary() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.library));
}

function recordToGenome(skill) {
  return {
    ...skill.genome,
    repository: {
      id: skill.id,
      status: skill.status,
      currentVersionId: skill.currentVersionId,
      versions: skill.versions ?? [],
      evaluations: skill.evaluations ?? [],
      snapshots: skill.snapshots ?? [],
    },
  };
}

async function syncRepository() {
  const { skills } = await listSkills();
  state.library = skills.map(recordToGenome);
  saveLibrary();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortDate(value) {
  if (!value) return "未知";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(
    new Date(value),
  );
}

function setNotice(message, tone = "success") {
  state.notice = { message, tone };
}

function renderHeader() {
  return `
    <header class="discovery-nav">
      <a class="brand" href="./index.html" aria-label="返回 RogueSkills">
        <span class="brand-mark">R</span>
        <span><strong>RogueSkills</strong><small>DISCOVERY OBSERVATORY</small></span>
      </a>
      <nav class="discovery-tabs" aria-label="Discovery 导航">
        <button class="${state.view === "search" ? "active" : ""}" data-action="switch-view" data-view="search">统一搜索</button>
        <button class="${state.view === "convert" ? "active" : ""}" data-action="switch-view" data-view="convert">SOP 转换</button>
        <button class="${state.view === "library" ? "active" : ""}" data-action="switch-view" data-view="library">
          Skill Repository <span>${state.library.length}</span>
        </button>
      </nav>
      <a class="back-to-run" href="./index.html">${state.gateway === "online" ? "GATEWAY ONLINE" : "LOCAL FALLBACK"} · Evolution Run <b>→</b></a>
    </header>`;
}

function renderNotice() {
  if (!state.notice) return "";
  return `<div class="discovery-notice ${state.notice.tone}"><span>${state.notice.tone === "error" ? "!" : "✓"}</span>${escapeHtml(state.notice.message)}</div>`;
}

function renderConnector(connector) {
  const selectable = ["live", "beta"].includes(connector.status) && connector.mode !== "upload";
  const selected = state.sourceIds.has(connector.id);
  return `
    <button class="connector-card ${selected ? "selected" : ""} ${!selectable ? "disabled" : ""}"
      ${selectable ? `data-action="toggle-source" data-source-id="${connector.id}"` : "disabled"}>
      <span class="connector-mark">${connector.shortName}</span>
      <span class="connector-copy"><strong>${connector.name}</strong><small>${connector.description}</small></span>
      <span class="connector-state ${connector.status}">${connector.status === "live" ? "LIVE" : connector.status === "beta" ? "BETA" : "NEXT"}</span>
      ${selectable ? `<i>${selected ? "✓" : "+"}</i>` : ""}
    </button>`;
}

function renderProviderStatus() {
  if (!state.providerStatus.length) return "";
  return `<div class="provider-status-row">${state.providerStatus.map((item) => {
    const connector = connectorById(item.sourceId);
    return `<div class="provider-status ${item.state}"><span>${connector?.shortName ?? item.sourceId}</span><strong>${item.state === "ok" ? `${item.count} results` : item.message ?? "暂不可用"}</strong></div>`;
  }).join("")}</div>`;
}

function candidateInLibrary(candidate) {
  return state.library.some(
    (genome) => genome.discovery?.candidateId === candidate.id || genome.provenance?.url === candidate.url,
  );
}

function renderCandidate(candidate) {
  const staged = candidateInLibrary(candidate);
  const staging = state.stagingId === candidate.id;
  const risk = candidate.risk ?? { level: "medium", reasons: [] };
  return `
    <article class="candidate-card">
      <div class="candidate-source">
        <span>${escapeHtml(connectorById(candidate.sourceId)?.shortName ?? candidate.sourceId)}</span>
        <small>${escapeHtml(candidate.platform)}</small><i></i><small>${escapeHtml(candidate.kind.toUpperCase())}</small>
        ${candidate.signals?.official ? `<em>VERIFIED ORG</em>` : ""}
      </div>
      <div class="candidate-main">
        <div class="candidate-copy">
          <div class="candidate-title-line"><h3>${escapeHtml(candidate.name)}</h3><span class="risk-badge ${risk.level}">${risk.level} risk</span></div>
          <p>${escapeHtml(candidate.summary)}</p>
          <div class="candidate-meta">
            <span>by ${escapeHtml(candidate.author)}</span><span>更新 ${shortDate(candidate.updatedAt)}</span>
            <span>License: ${escapeHtml(candidate.license)}</span>
            ${candidate.signals?.stars ? `<span>★ ${candidate.signals.stars.toLocaleString()}</span>` : ""}
          </div>
          <div class="candidate-tags">${(candidate.tags ?? []).slice(0, 7).map((tag) => `<span>#${escapeHtml(tag)}</span>`).join("")}</div>
        </div>
        <div class="candidate-score"><strong>${candidate.ranking.total}</strong><small>DISCOVERY SCORE</small><i><b style="width:${candidate.ranking.total}%"></b></i></div>
      </div>
      <div class="score-breakdown">
        <div><span>相关度</span><strong>${candidate.ranking.relevance}</strong></div>
        <div><span>质量</span><strong>${candidate.ranking.quality}</strong></div>
        <div><span>可信度</span><strong>${candidate.ranking.trust}</strong></div>
        <div><span>可转换性</span><strong>${candidate.ranking.convertibility}</strong></div>
      </div>
      <div class="candidate-actions">
        <span>${risk.reasons[0] ? escapeHtml(risk.reasons[0]) : "静态扫描未发现高风险模式"}</span>
        <div>
          ${candidate.url ? `<a href="${escapeHtml(candidate.url)}" target="_blank" rel="noreferrer">查看来源 ↗</a>` : ""}
          <button class="stage-button ${staged ? "staged" : ""}" data-action="stage-candidate" data-candidate-id="${candidate.id}" ${staged || staging ? "disabled" : ""}>
            ${staging ? "拉取快照中…" : staged ? "已在隔离区" : "拉取并转换"}
          </button>
        </div>
      </div>
    </article>`;
}

function renderSearchView() {
  const kinds = [["all", "全部"], ["skill", "Skill"], ["sop", "SOP"], ["runbook", "Runbook"], ["checklist", "Checklist"], ["material", "材料"]];
  const visible = state.kindFilter === "all" ? state.results : state.results.filter((item) => item.kind === state.kindFilter);
  return `
    <section class="discovery-hero">
      <div><p>FEDERATED SKILL SEARCH</p><h1>从已有能力和行业知识中<br /><em>发现下一代 Skill 的起点</em></h1><span>搜索只产生候选，不会安装或执行任何外部内容。</span></div>
      <div class="discovery-stats">
        <div><strong>${SOURCE_CONNECTORS.filter((item) => item.status !== "planned").length}</strong><span>可用连接器</span></div>
        <div><strong>${state.results.length}</strong><span>本次召回</span></div>
        <div><strong>${state.library.length}</strong><span>隔离候选</span></div>
      </div>
    </section>
    <section class="search-console">
      <div class="search-box"><span>⌕</span><input id="discovery-query" value="${escapeHtml(state.query)}" placeholder="描述能力、业务目标或失败模式…" autocomplete="off" /><button data-action="run-search" ${state.searching ? "disabled" : ""}>${state.searching ? "正在检索…" : "跨源搜索"}<b>→</b></button></div>
      <div class="query-examples"><span>查询语法</span>
        <button data-action="use-query" data-query="browser extraction source:github type:skill">browser extraction source:github</button>
        <button data-action="use-query" data-query="客服 升级 SOP type:sop">客服升级 SOP</button>
        <button data-action="use-query" data-query="incident response tag:security">incident response tag:security</button>
      </div>
    </section>
    <section class="connector-section">
      <div class="section-heading"><div><span>SEARCH ROUTER</span><h2>选择数据来源</h2></div><p>官方组织预设仍通过 GitHub 公共接口检索；平台专用连接器会逐步替换。</p></div>
      <div class="connector-grid">${SOURCE_CONNECTORS.map(renderConnector).join("")}</div>${renderProviderStatus()}
    </section>
    <section class="result-section">
      <div class="result-toolbar"><div><span>DISCOVERY RESULTS</span><h2>${state.searching ? "正在聚合来源…" : `${visible.length} 个候选`}</h2></div>
        <div class="kind-filters">${kinds.map(([id, label]) => `<button class="${state.kindFilter === id ? "active" : ""}" data-action="filter-kind" data-kind="${id}">${label}</button>`).join("")}</div>
      </div>
      <div class="candidate-list">${visible.length ? visible.map(renderCandidate).join("") : `<div class="empty-state"><span>⌕</span><h3>${state.searching ? "正在查询所选来源" : "没有匹配的候选"}</h3><p>尝试减少过滤器，或者切换到 SOP 转换导入自己的材料。</p></div>`}</div>
    </section>`;
}

function renderGenomePreview(genome) {
  if (!genome) return `<div class="genome-empty"><span>DNA</span><h3>等待材料转换</h3><p>转换结果会显示抽取出的目标、Workflow、约束、工具、完整度和安全风险。</p></div>`;
  return `
    <div class="genome-preview">
      <div class="genome-heading"><div><span>SKILL GENOME · ${genome.schemaVersion}</span><h2>${escapeHtml(genome.name)}</h2></div><div class="completeness-ring" style="--score:${genome.metadata.completeness * 3.6}deg"><strong>${genome.metadata.completeness}</strong><small>完整度</small></div></div>
      <p class="genome-description">${escapeHtml(genome.description)}</p>
      <div class="genome-status-row"><span class="quarantine-tag">QUARANTINE</span><span class="risk-badge ${genome.risk.level}">${genome.risk.level} risk</span><span>${escapeHtml(genome.metadata.license)}</span></div>
      <div class="genome-block"><span>WORKFLOW · ${genome.workflow.steps.length} STEPS</span><ol>${genome.workflow.steps.map((step) => `<li><b>${step.order}</b><p>${escapeHtml(step.instruction)}</p></li>`).join("") || `<li class="missing">没有识别出明确步骤，需要人工补充。</li>`}</ol></div>
      <div class="genome-columns">
        <div class="genome-block"><span>CONSTRAINTS</span><ul>${genome.constraints.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || `<li class="missing">未识别</li>`}</ul></div>
        <div class="genome-block"><span>TOOLS</span><div class="tool-list">${genome.tools.map((tool) => `<i>${escapeHtml(tool)}</i>`).join("") || `<i>未声明</i>`}</div></div>
      </div>
      <div class="gate-list">${genome.evaluation.requiredGates.map((gate) => `<div><span>○</span><strong>${escapeHtml(gate)}</strong><small>NOT RUN</small></div>`).join("")}</div>
      <button class="primary-button" data-action="stage-preview">保存到隔离候选库 <b>→</b></button>
    </div>`;
}

function renderConvertView() {
  return `
    <section class="subpage-heading">
      <div><p>SOP → SKILL GENOME</p><h1>把领域知识变成可评估的能力候选</h1><span>材料完全在本地解析；示例命令不会被执行。</span></div>
      <div class="pipeline-mini"><span>材料</span><i>→</i><span>结构抽取</span><i>→</i><span>风险扫描</span><i>→</i><span>隔离评测</span></div>
    </section>
    <section class="converter-grid">
      <article class="material-editor">
        <div class="section-heading compact"><div><span>SOURCE MATERIAL</span><h2>输入 SOP 或操作材料</h2></div></div>
        <label class="field-label" for="material-title">候选名称</label><input class="text-field" id="material-title" value="${escapeHtml(state.uploadedName)}" placeholder="例如：客户退款审核 SOP" />
        <div class="field-row"><div><label class="field-label" for="material-source">来源说明</label><input class="text-field" id="material-source" placeholder="内部知识库 / URL / 团队" /></div>
          <div><label class="field-label" for="material-license">许可证</label><select class="text-field" id="material-license"><option value="unknown">未知</option><option value="internal">内部授权</option><option value="MIT">MIT</option><option value="Apache-2.0">Apache-2.0</option><option value="CC-BY-4.0">CC-BY-4.0</option></select></div></div>
        <label class="field-label" for="material-content">Markdown / 纯文本</label><textarea id="material-content" placeholder="# 目标\n\n描述这个流程解决的问题。\n\n## 步骤\n1. …\n2. …\n\n## 约束\n- 必须…\n- 不得…">${escapeHtml(state.uploadedText)}</textarea>
        <div class="editor-actions"><label class="file-button"><input id="material-file" type="file" accept=".md,.txt,text/markdown,text/plain" />上传 .md / .txt</label><span>${state.uploadedText.length.toLocaleString()} chars · 本地处理</span><button class="convert-button" data-action="convert-material">转换为 Skill Genome <b>→</b></button></div>
        <div class="conversion-boundary"><span>安全边界</span><p>当前转换器只识别结构并生成候选。它不会运行材料中的脚本，也不会把候选直接放进生产 Skill Hub。</p></div>
      </article>
      <article class="genome-panel">${renderGenomePreview(state.preview)}</article>
    </section>`;
}

function renderLibraryItem(genome) {
  const source = genome.provenance ?? {};
  const steps = genome.workflow?.steps?.length ?? 0;
  const repository = genome.repository ?? null;
  const status = repository?.status ?? genome.status;
  const admission = repository?.evaluations?.find(
    (evaluation) => evaluation.benchmarkId === "library-admission-v1" && evaluation.passed,
  );
  const statusLabel =
    status === "initial"
      ? "INITIAL SKILL LIBRARY"
      : admission
        ? "BENCHMARK PASSED · READY TO PROMOTE"
        : "WAITING FOR ADMISSION BENCHMARK";
  const displayedScore = genome.evaluation.score ?? admission?.score ?? genome.metadata.completeness;
  const displayedScoreLabel = genome.evaluation.score != null || admission ? "准入分" : "完整度";
  return `
    <article class="library-item">
      <div class="library-item-main"><span class="library-icon">${status === "initial" ? "IN" : "SK"}</span><div><div class="library-title"><h3>${escapeHtml(genome.name)}</h3><span class="risk-badge ${genome.risk.level}">${genome.risk.level}</span><span class="repository-status ${status}">${status}</span></div><p>${escapeHtml(genome.description)}</p><div class="library-meta"><span>${escapeHtml(source.platform)}</span><span>${steps} workflow steps</span><span>${repository?.versions?.length ?? 1} versions</span><span>fingerprint ${escapeHtml(source.fingerprint)}</span></div></div><div class="library-score"><strong>${displayedScore}</strong><small>${displayedScoreLabel}</small></div></div>
      <div class="library-gates">${genome.evaluation.requiredGates.map((gate) => `<span><i></i>${escapeHtml(gate)}</span>`).join("")}</div>
      <div class="library-actions"><span>状态：<b>${statusLabel}</b></span><div>
        ${status === "quarantine" && state.gateway === "online" ? `<button class="benchmark-button" data-action="benchmark-genome" data-genome-id="${genome.id}">运行准入 Benchmark</button>` : ""}
        ${status === "quarantine" && admission && state.gateway === "online" ? `<button class="promote-button" data-action="promote-genome" data-genome-id="${genome.id}" data-evaluation-id="${admission.id}">晋升 Initial Library</button>` : ""}
        <button data-action="export-genome" data-genome-id="${genome.id}">导出 JSON</button>
        ${status === "quarantine" ? `<button class="remove" data-action="remove-genome" data-genome-id="${genome.id}">移除</button>` : ""}
      </div></div>
    </article>`;
}

function renderLibraryView() {
  const highRisk = state.library.filter((item) => item.risk.level === "high").length;
  const initialCount = state.library.filter((item) => (item.repository?.status ?? item.status) === "initial").length;
  return `
    <section class="subpage-heading library-heading"><div><p>VERSIONED SKILL REPOSITORY</p><h1>Skill Repository</h1><span>候选、版本、来源快照与准入评估已经持久化；只有 Initial Skill 可以进入 Evolution Run。</span></div><div class="library-overview"><div><strong>${state.library.length}</strong><span>全部 Skill</span></div><div><strong>${initialCount}</strong><span>Initial Library</span></div><div><strong>${highRisk}</strong><span>高风险</span></div></div></section>
    <section class="library-layout"><aside class="gate-explainer"><span>RELEASE GATES</span><h2>候选进入初始库前</h2><ol>
      <li><b>01</b><div><strong>Static Safety</strong><small>注入、Secret 与危险脚本扫描</small></div></li><li><b>02</b><div><strong>License Review</strong><small>确认允许保存、改写与分发</small></div></li><li><b>03</b><div><strong>Benchmark</strong><small>公开、Validation 与 Hidden Test</small></div></li><li><b>04</b><div><strong>Human Review</strong><small>确认业务边界和评估结论</small></div></li></ol><p>隔离区内容永远不会被自动执行或部署。</p></aside>
      <div class="library-list">${state.library.length ? state.library.map(renderLibraryItem).join("") : `<div class="empty-state library-empty"><span>0</span><h3>Repository 还是空的</h3><p>从统一搜索拉取已有 Skill，或把自己的 SOP 转换成候选。</p><button data-action="switch-view" data-view="search">开始发现 Skill →</button></div>`}</div></section>`;
}

function render() {
  document.title = `RogueSkills · ${state.view === "search" ? "Skill Discovery" : state.view === "convert" ? "SOP Converter" : "Skill Repository"}`;
  const content = state.view === "search" ? renderSearchView() : state.view === "convert" ? renderConvertView() : renderLibraryView();
  root.innerHTML = `<main class="discovery-shell">${renderHeader()}${renderNotice()}${content}<footer class="discovery-footer"><span>${state.gateway === "online" ? "SQLITE REPOSITORY · SEARCH GATEWAY ONLINE" : "LOCAL FALLBACK · GATEWAY OFFLINE"}</span><a href="./docs/skill-discovery-design.md">Discovery protocol v0.1</a></footer></main>`;
}

async function runSearch() {
  state.query = document.querySelector("#discovery-query")?.value.trim() || state.query;
  const requestedSources = parseSearchQuery(state.query).filters.source.filter((sourceId) =>
    SOURCE_CONNECTORS.some(
      (connector) => connector.id === sourceId && ["live", "beta"].includes(connector.status),
    ),
  );
  if (requestedSources.length) state.sourceIds = new Set(requestedSources);
  state.searching = true;
  state.notice = null;
  render();
  let results;
  let status;
  try {
    if (state.gateway !== "online") throw new Error("Gateway offline");
    ({ results, status } = await searchDiscovery(state.query, [...state.sourceIds]));
  } catch {
    ({ results, status } = localFallbackSearch(state.query, [...state.sourceIds]));
  }
  state.results = results;
  state.providerStatus = status;
  state.searching = false;
  if (status.every((item) => item.state !== "ok")) setNotice("所选远程来源当前不可用，请保留种子索引或稍后重试。", "error");
  render();
}

function downloadGenome(genome) {
  const blob = new Blob([JSON.stringify(genome, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${genome.id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

root.addEventListener("click", async (event) => {
  const trigger = event.target.closest("[data-action]");
  if (!trigger) return;
  const action = trigger.dataset.action;
  if (action === "switch-view") { state.view = trigger.dataset.view; state.notice = null; render(); return; }
  if (action === "toggle-source") { const id = trigger.dataset.sourceId; state.sourceIds.has(id) ? state.sourceIds.delete(id) : state.sourceIds.add(id); if (!state.sourceIds.size) state.sourceIds.add("builtin"); render(); return; }
  if (action === "use-query") { state.query = trigger.dataset.query; render(); return; }
  if (action === "run-search") { await runSearch(); return; }
  if (action === "filter-kind") { state.kindFilter = trigger.dataset.kind; render(); return; }
  if (action === "stage-candidate") {
    const candidate = state.results.find((item) => item.id === trigger.dataset.candidateId);
    if (!candidate) return;
    state.stagingId = candidate.id; state.notice = null; render();
    try {
      let genome;
      if (state.gateway === "online") {
        const { skill } = await importDiscoveryCandidate(candidate);
        genome = recordToGenome(skill);
      } else {
        genome = await candidateToSkillGenome(candidate);
      }
      state.library = [genome, ...state.library.filter((item) => item.id !== genome.id)];
      saveLibrary();
      setNotice(`「${genome.name}」已保存到隔离候选库。`);
    }
    catch (error) { setNotice(`候选转换失败：${error.message}`, "error"); }
    state.stagingId = null; render(); return;
  }
  if (action === "convert-material") {
    const title = document.querySelector("#material-title")?.value.trim();
    const sourceLabel = document.querySelector("#material-source")?.value.trim();
    const license = document.querySelector("#material-license")?.value;
    const content = document.querySelector("#material-content")?.value.trim();
    if (!content) { setNotice("请先粘贴或上传 SOP 材料。", "error"); render(); return; }
    state.uploadedName = title; state.uploadedText = content;
    state.preview = convertMaterialToSkill({ title, content, license, source: { platform: sourceLabel || "Manual SOP", author: "Local User" } });
    state.notice = null; render(); return;
  }
  if (action === "stage-preview" && state.preview) {
    let genome = state.preview;
    try {
      if (state.gateway === "online") {
        const { skill } = await storeSkillGenome(state.preview, "manual");
        genome = recordToGenome(skill);
      }
      state.library = [genome, ...state.library.filter((item) => item.id !== genome.id)];
      saveLibrary();
      setNotice(`「${genome.name}」已保存到 Skill Repository。`);
    } catch (error) {
      setNotice(`保存失败：${error.message}`, "error");
    }
    render();
    return;
  }
  if (action === "benchmark-genome") {
    try {
      const { result } = await benchmarkSkill(trigger.dataset.genomeId);
      await syncRepository();
      setNotice(
        result.passed
          ? `准入 Benchmark 通过，得分 ${result.score}。请人工确认后晋升。`
          : `准入 Benchmark 未通过，得分 ${result.score}。`,
        result.passed ? "success" : "error",
      );
    } catch (error) {
      setNotice(`Benchmark 失败：${error.message}`, "error");
    }
    render();
    return;
  }
  if (action === "promote-genome") {
    try {
      await promoteSkill(trigger.dataset.genomeId, trigger.dataset.evaluationId);
      await syncRepository();
      setNotice("Skill 已进入 Initial Skill Library，可以在 Evolution Run 中选择。", "success");
    } catch (error) {
      setNotice(`晋升失败：${error.message}`, "error");
    }
    render();
    return;
  }
  if (action === "remove-genome") {
    try {
      if (state.gateway === "online") await deleteSkill(trigger.dataset.genomeId);
      state.library = state.library.filter((item) => item.id !== trigger.dataset.genomeId);
      saveLibrary();
    } catch (error) {
      setNotice(`移除失败：${error.message}`, "error");
    }
    render();
    return;
  }
  if (action === "export-genome") { const genome = state.library.find((item) => item.id === trigger.dataset.genomeId); if (genome) downloadGenome(genome); }
});

root.addEventListener("keydown", (event) => { if (event.key === "Enter" && event.target.id === "discovery-query") runSearch(); });
root.addEventListener("change", async (event) => {
  if (event.target.id !== "material-file") return;
  const file = event.target.files?.[0];
  if (!file) return;
  state.uploadedText = await file.text(); state.uploadedName = file.name.replace(/\.(?:md|txt)$/i, ""); state.preview = null; render();
});

async function initialize() {
  render();
  try {
    await apiHealth();
    state.gateway = "online";
    await syncRepository();
    const { results, status } = await searchDiscovery(state.query, ["builtin"]);
    state.results = results;
    state.providerStatus = status;
  } catch {
    state.gateway = "offline";
    const { results, status } = localFallbackSearch(state.query, ["builtin"]);
    state.results = results;
    state.providerStatus = status;
  }
  render();
}

initialize();
