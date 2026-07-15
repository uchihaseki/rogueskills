import {
  ARCHETYPES,
  EVOLUTIONS,
  NODE_TYPES,
  RUN_MODES,
  STAT_LABELS,
} from "../core/evolution/catalog.js";
import {
  MAX_STABILITY,
  SAVE_VERSION,
  calculateObjectiveScore,
  chooseMutation,
  createRun,
  getCurrentLayer,
  getCurrentRegion,
  getEvolutionById,
  getEvolutionProgress,
  getMonsterById,
  getMutationById,
  getSelectedNode,
  resolveCurrentNode,
  selectNode,
  skipMutation,
} from "../core/evolution/engine.js";
import { listInitialSkills } from "./api-client.js";
import { capabilityProfileFromGenome } from "../core/genome/skill-genome.js";

const STORAGE_KEY = "rogueskills.prototype.run.v1";
const root = document.querySelector("#app");

let savedRun = loadRun();
let run = null;
let initialSkills = [];
let initialLibraryState = "loading";
let selectedInitialSkillId = null;

function loadRun() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return parsed?.saveVersion === SAVE_VERSION ? parsed : null;
  } catch {
    return null;
  }
}

function persistRun() {
  if (run) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(run));
    savedRun = run;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function effectMarkup(effects) {
  return Object.entries(effects)
    .map(([stat, value]) => {
      const sign = value > 0 ? "+" : "";
      const tone = value > 0 ? "positive" : "negative";
      return `<span class="effect ${tone}">${STAT_LABELS[stat] ?? stat} ${sign}${value}</span>`;
    })
    .join("");
}

function makeSeed() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const part = Array.from({ length: 5 }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join("");
  return `RUN-${part}`;
}

function renderSetup() {
  const archetype = ARCHETYPES.browser;
  const selectedSkill =
    initialSkills.find((skill) => skill.id === selectedInitialSkillId) ?? initialSkills[0] ?? null;
  const genome = selectedSkill?.genome ?? null;
  const displayName = genome?.name ?? archetype.name;
  const displayRole = genome?.metadata?.category ?? archetype.role;
  const displayDescription = genome?.description ?? archetype.description;
  const displayWeapons = genome?.tools?.length ? genome.tools : archetype.initialWeapons;
  const displayStats = genome ? capabilityProfileFromGenome(genome) : archetype.stats;
  document.title = "RogueSkills · 新建 Evolution Run";

  root.innerHTML = `
    <main class="setup-shell">
      <header class="landing-nav">
        <a class="brand" href="#" aria-label="RogueSkills 首页">
          <span class="brand-mark">R</span>
          <span>
            <strong>RogueSkills</strong>
            <small>EVOLUTION LAB</small>
          </span>
        </a>
        <div class="nav-actions">
          <a class="discovery-link" href="./discovery.html">发现 Skill <b>⌕</b></a>
          <div class="prototype-pill"><span></span> Core prototype · v0.1</div>
        </div>
      </header>

      <section class="hero">
        <p class="eyebrow">A ROGUELIKE SKILL EVOLUTION PROTOCOL</p>
        <h1>把一次 Skill 优化<br /><em>变成一场可重放的冒险</em></h1>
        <p class="hero-copy">
          穿过由真实业务失败模式组成的地图，在有限 Stability、Compute 和 Complexity 中构筑能力，
          最终通过隔离的隐藏验收。
        </p>
      </section>

      <section class="setup-grid">
        <article class="setup-card archetype-card">
          <div class="card-kicker">01 · 选择基础角色</div>
          <div class="initial-library-list">
            ${
              initialSkills.length
                ? initialSkills
                    .map(
                      (skill) => `<button class="library-skill-button ${skill.id === selectedSkill?.id ? "selected" : ""}" data-action="select-base-skill" data-skill-id="${escapeHtml(skill.id)}">
                        <span>${escapeHtml(skill.genome.metadata.category)}</span>
                        <strong>${escapeHtml(skill.name)}</strong>
                        <small>v${skill.versions?.[0]?.version ?? 1} · ${skill.genome.evaluation.score ?? "—"} score</small>
                      </button>`,
                    )
                    .join("")
                : `<div class="library-status ${initialLibraryState}">${
                    initialLibraryState === "loading"
                      ? "正在读取 Initial Skill Library…"
                      : "Gateway 离线，使用内置 Browser Skill。"
                  }</div>`
            }
          </div>
          <div class="archetype-heading">
            <div class="role-orb"><span>BR</span></div>
            <div>
              <h2>${escapeHtml(displayName)}</h2>
              <p>${escapeHtml(displayRole)}</p>
            </div>
            <span class="selected-badge">INITIAL</span>
          </div>
          <p class="card-description">${escapeHtml(displayDescription)}</p>
          <div class="loadout">
            <span class="section-label">初始武器</span>
            <div class="chip-row">
              ${displayWeapons.map((weapon) => `<span class="weapon-chip">${escapeHtml(weapon)}</span>`).join("")}
            </div>
          </div>
          <div class="mini-stats">
            ${Object.entries(displayStats)
              .map(
                ([stat, value]) => `
                  <div>
                    <span>${STAT_LABELS[stat]}</span>
                    <strong>${value}</strong>
                    <i><b style="width:${value}%"></b></i>
                  </div>`,
              )
              .join("")}
          </div>
        </article>

        <article class="setup-card run-config-card">
          <div class="card-kicker">02 · 定义本局目标</div>
          <div class="mode-options">
            ${Object.values(RUN_MODES)
              .map(
                (mode, index) => `
                  <label class="mode-option">
                    <input type="radio" name="mode" value="${mode.id}" ${index === 0 ? "checked" : ""} />
                    <span class="mode-radio"></span>
                    <span class="mode-copy">
                      <strong>${mode.name}</strong>
                      <small>${mode.description}</small>
                    </span>
                  </label>`,
              )
              .join("")}
          </div>

          <div class="seed-block">
            <label for="run-seed">地图 Seed</label>
            <div class="seed-input-wrap">
              <input id="run-seed" value="ROGUE-0714" spellcheck="false" maxlength="32" />
              <button class="icon-button" data-action="random-seed" aria-label="随机 Seed">↻</button>
            </div>
            <p>相同 Seed 会生成相同地图；相同构筑也会得到相同评估。</p>
          </div>

          <button class="primary-button large" data-action="start-run">
            <span>生成 Evolution Run</span><b>→</b>
          </button>
          ${
            savedRun
              ? `<button class="secondary-button continue-button" data-action="continue-run">
                   继续上次 Run · 第 ${savedRun.actIndex + 1} 幕 · ${escapeHtml(savedRun.seed)}
                 </button>`
              : ""
          }
        </article>
      </section>

      <section class="protocol-strip">
        <div><span>01</span><strong>随机地图</strong><small>受业务覆盖约束</small></div>
        <i></i>
        <div><span>02</span><strong>失败遭遇</strong><small>怪物即失败模式</small></div>
        <i></i>
        <div><span>03</span><strong>能力构筑</strong><small>每次升级都有代价</small></div>
        <i></i>
        <div><span>04</span><strong>隐藏验收</strong><small>通关只获得候选资格</small></div>
      </section>

      <footer class="landing-footer">
        Skill Genome 1.0 · Deterministic Benchmark Runner · SQLite Lineage Repository
      </footer>
    </main>
  `;
}

function renderHud() {
  const region = getCurrentRegion(run) ?? run.map.at(-1);
  const stabilityPercent = Math.max(0, (run.stability / MAX_STABILITY) * 100);
  const complexityPercent = Math.min(100, (run.complexityUsed / run.complexityMax) * 100);

  return `
    <section class="hud">
      <div class="hud-card act-hud">
        <span class="hud-icon">A${run.actIndex + 1}</span>
        <div><small>当前区域</small><strong>${region.name}</strong></div>
      </div>
      <div class="hud-card">
        <span class="hud-icon integrity">♥</span>
        <div class="resource-copy">
          <small>STABILITY</small><strong>${run.stability}<i> / ${MAX_STABILITY}</i></strong>
          <span class="resource-bar danger"><b style="width:${stabilityPercent}%"></b></span>
        </div>
      </div>
      <div class="hud-card">
        <span class="hud-icon compute">C</span>
        <div class="resource-copy">
          <small>COMPUTE</small><strong>${run.compute}<i> units</i></strong>
          <span class="resource-bar compute-bar"><b style="width:${Math.min(100, run.compute)}%"></b></span>
        </div>
      </div>
      <div class="hud-card">
        <span class="hud-icon complexity">◇</span>
        <div class="resource-copy">
          <small>COMPLEXITY</small><strong>${run.complexityUsed}<i> / ${run.complexityMax}</i></strong>
          <span class="resource-bar complexity-bar"><b style="width:${complexityPercent}%"></b></span>
        </div>
      </div>
      <div class="hud-card score-hud">
        <small>OBJECTIVE SCORE</small>
        <strong>${calculateObjectiveScore(run)}</strong>
        <span>${RUN_MODES[run.modeId].name}</span>
      </div>
    </section>
  `;
}

function renderStats() {
  return `
    <div class="stat-list">
      ${Object.entries(run.stats)
        .map(
          ([stat, value]) => `
            <div class="stat-row">
              <span>${STAT_LABELS[stat]}</span>
              <i><b style="width:${value}%"></b></i>
              <strong>${value}</strong>
            </div>`,
        )
        .join("")}
    </div>
  `;
}

function renderBuildPanel() {
  const mutations = run.mutationIds.map(getMutationById).filter(Boolean);
  const evolutions = run.evolutionIds.map(getEvolutionById).filter(Boolean);
  const recipes = getEvolutionProgress(run)
    .filter((item) => !item.unlocked)
    .sort((left, right) => right.progress / right.total - left.progress / left.total)
    .slice(0, 3);

  return `
    <aside class="panel build-panel">
      <div class="panel-heading">
        <div><span>SKILL GENOME</span><h2>当前构筑</h2></div>
        <span class="build-count">${run.mutationIds.length} MUT</span>
      </div>

      <div class="build-section">
        <span class="section-label">基础武器</span>
        <div class="base-weapons">
          ${run.initialWeapons.map((weapon, index) => `<div><b>0${index + 1}</b><span>${weapon}</span></div>`).join("")}
        </div>
      </div>

      <div class="build-section">
        <span class="section-label">能力属性</span>
        ${renderStats()}
      </div>

      <div class="build-section mutation-stack-section">
        <span class="section-label">已装配 Mutation</span>
        <div class="mutation-stack">
          ${
            mutations.length
              ? mutations
                  .map(
                    (mutation) => `
                      <div class="equipped-mutation">
                        <span class="rarity-dot ${mutation.rarity}"></span>
                        <div><strong>${mutation.name}</strong><small>${mutation.category} · ${mutation.tags.join(" / ")}</small></div>
                        <b>${mutation.complexityCost}</b>
                      </div>`,
                  )
                  .join("")
              : `<p class="empty-copy">尚未装配能力。通过第一个遭遇获得 Mutation。</p>`
          }
        </div>
      </div>

      <div class="build-section evolution-section">
        <span class="section-label">武器进化</span>
        ${
          evolutions.length
            ? `<div class="unlocked-evolutions">
                ${evolutions
                  .map(
                    (evolution) => `
                      <div class="evolution-badge">
                        <span>✦</span><div><strong>${evolution.name}</strong><small>${evolution.subtitle}</small></div>
                      </div>`,
                  )
                  .join("")}
              </div>`
            : ""
        }
        <div class="recipe-list">
          ${recipes
            .map(
              (recipe) => `
                <div class="recipe">
                  <div><strong>${recipe.name}</strong><span>${recipe.progress}/${recipe.total}</span></div>
                  <i><b style="width:${(recipe.progress / recipe.total) * 100}%"></b></i>
                  <small>${recipe.requirements.map((item) => `${item.tag} ${item.current}/${item.required}`).join(" · ")}</small>
                </div>`,
            )
            .join("")}
        </div>
      </div>
    </aside>
  `;
}

function nodeState(node) {
  if (run.completedNodeIds.includes(node.id)) return "completed";
  if (run.selectedNodeId === node.id) return "selected";
  if (node.layer < run.layerIndex) return "skipped";
  if (node.layer === run.layerIndex && run.phase === "choose_node" && run.status === "active") return "available";
  return "locked";
}

function renderNode(node) {
  const type = NODE_TYPES[node.type];
  const monster = node.monsterId ? getMonsterById(node.monsterId) : null;
  const state = nodeState(node);
  const isHiddenBoss = node.type === "boss" && state === "locked";
  const title = isHiddenBoss
    ? "隐藏验收"
    : monster
      ? monster.name
      : node.type === "lab"
        ? "进化实验室"
        : "安全节点";
  const subtitle = isHiddenBoss
    ? "数据与规则未公开"
    : monster
      ? monster.failureMode
      : type.description;

  return `
    <button
      class="map-node ${node.type} ${state}"
      ${state === "available" ? `data-action="select-node" data-node-id="${node.id}"` : "disabled"}
      aria-label="${title}"
    >
      <span class="node-symbol">${state === "completed" ? "✓" : type.symbol}</span>
      <span class="node-copy">
        <small>${type.name} · D${node.difficulty}</small>
        <strong>${title}</strong>
        <em>${subtitle}</em>
      </span>
      ${state === "available" ? `<span class="node-enter">选择 →</span>` : ""}
    </button>
  `;
}

function renderMap() {
  const region = getCurrentRegion(run) ?? run.map.at(-1);

  return `
    <section class="panel map-panel">
      <div class="region-heading">
        <div>
          <span>ACT ${region.act} · BUSINESS SCENARIO MAP</span>
          <h1>${region.name}</h1>
          <p>${region.description}</p>
        </div>
        <div class="region-seed"><small>MAP SEED</small><strong>${escapeHtml(run.seed)}</strong></div>
      </div>
      <div class="map-stage">
        <div class="map-grid">
          ${region.layers
            .map(
              (layer, layerIndex) => `
                <div class="map-layer ${layerIndex === run.layerIndex ? "current" : ""}">
                  <div class="layer-label"><span>${String(layerIndex + 1).padStart(2, "0")}</span><small>${
                    layerIndex === region.layers.length - 1 ? "BOSS" : "ROUTE"
                  }</small></div>
                  <div class="layer-nodes">${layer.map(renderNode).join("")}</div>
                  ${layerIndex < region.layers.length - 1 ? `<span class="path-line">→</span>` : ""}
                </div>`,
            )
            .join("")}
        </div>
      </div>
      <div class="map-legend">
        <span><i class="normal"></i>普通 Benchmark</span>
        <span><i class="elite"></i>精英验证</span>
        <span><i class="utility"></i>实验 / 休息</span>
        <span><i class="boss"></i>Hidden Test</span>
      </div>
    </section>
  `;
}

function renderResult(result) {
  if (!result || result.kind) return "";

  return `
    <div class="evaluation-result ${result.passed ? "passed" : "failed"}">
      <div class="result-verdict">
        <span>${result.passed ? "PASS" : "FAIL"}</span>
        <div><small>BUSINESS COVERAGE</small><strong>${result.coverage}% <i>/ ${result.threshold}%</i></strong></div>
      </div>
      <div class="metric-grid">
        <div><small>质量</small><strong>${result.quality}</strong></div>
        <div><small>P95 延迟</small><strong>${result.latency}s</strong></div>
        <div><small>评估消耗</small><strong>${result.computeCost}</strong></div>
        <div><small>能力 / 难度</small><strong>${result.capability} / ${result.difficulty}</strong></div>
      </div>
      <div class="benchmark-case-list">
        ${result.cases
          .map(
            (item) => `<div class="${item.passed ? "passed" : "failed"}"><span>${item.passed ? "✓" : "×"}</span><strong>${item.label}</strong><small>${item.score}</small></div>`,
          )
          .join("")}
      </div>
      ${
        !result.securityGatePassed
          ? `<p class="security-warning">安全门槛未通过：构筑缺少应对恶意输入或权限边界的能力。</p>`
          : ""
      }
    </div>
  `;
}

function renderMutationCard(mutationId) {
  const mutation = getMutationById(mutationId);
  if (!mutation) return "";

  return `
    <button class="mutation-card ${mutation.rarity}" data-action="choose-mutation" data-mutation-id="${mutation.id}">
      <div class="mutation-card-top">
        <span>${mutation.category}</span>
        <em>${mutation.rarity}</em>
      </div>
      <h3>${mutation.name}</h3>
      <div class="effect-row">${effectMarkup(mutation.effects)}</div>
      <p>${mutation.benefit}</p>
      <div class="tradeoff"><span>代价</span>${mutation.tradeoff}</div>
      <div class="mutation-card-foot">
        <span>${mutation.tags.map((tag) => `#${tag}`).join(" ")}</span>
        <strong>复杂度 ${mutation.complexityCost}</strong>
      </div>
    </button>
  `;
}

function renderEncounterPanel() {
  const node = getSelectedNode(run);
  if (!node) return renderChoosePrompt();
  const monster = node.monsterId ? getMonsterById(node.monsterId) : null;
  const type = NODE_TYPES[node.type];

  if (node.type === "rest") {
    return `
      <div class="action-content utility-content">
        <span class="encounter-kicker">SAFE NODE</span>
        <div class="utility-symbol">○</div>
        <h2>安全节点</h2>
        <p>修复当前实验分支，并补充下一阶段需要的评估预算。</p>
        <div class="utility-reward"><span>Stability</span><strong>最多 +3</strong><span>Compute</span><strong>+10</strong></div>
        <button class="primary-button" data-action="resolve-node">执行重整</button>
      </div>`;
  }

  if (node.type === "lab") {
    return `
      <div class="action-content utility-content lab-content">
        <span class="encounter-kicker">EVOLUTION LAB</span>
        <div class="utility-symbol">✦</div>
        <h2>进化实验室</h2>
        <p>跳过 Benchmark，直接根据当前构筑和业务目标生成一次 Mutation Draft。</p>
        <div class="lab-note">实验室不会恢复 Stability，选择仍会占用 Complexity。</div>
        <button class="primary-button" data-action="resolve-node">生成 Mutation</button>
      </div>`;
  }

  return `
    <div class="action-content encounter-content">
      <span class="encounter-kicker">${type.name.toUpperCase()} · D${node.difficulty}</span>
      <div class="monster-emblem ${node.type}"><span>${type.symbol}</span></div>
      <h2>${monster.name}</h2>
      <p class="failure-mode">${monster.failureMode}</p>
      <div class="business-case">
        <span>业务案例</span>
        <p>${monster.businessExample}</p>
      </div>
      <div class="requirement-list">
        <span>能力权重</span>
        ${Object.entries(monster.requirements)
          .map(
            ([stat, weight]) => `
              <div><span>${STAT_LABELS[stat]}</span><i><b style="width:${weight * 100}%"></b></i><strong>${Math.round(weight * 100)}%</strong></div>`,
          )
          .join("")}
      </div>
      ${monster.securityFloor ? `<div class="hard-gate">安全硬门槛：${monster.securityFloor}</div>` : ""}
      <button class="primary-button" data-action="resolve-node">
        ${node.type === "boss" ? "执行隐藏验收" : "运行 Benchmark"}<b>→</b>
      </button>
      <small class="deterministic-note">结果由 Seed、当前构筑和节点共同决定，可完整重放。</small>
    </div>
  `;
}

function renderChoosePrompt() {
  const currentLayer = getCurrentLayer(run);

  return `
    <div class="action-content choose-content">
      <span class="encounter-kicker">ROUTE DECISION</span>
      <div class="radar-mark"><i></i><i></i><span>${currentLayer.length}</span></div>
      <h2>选择下一条路线</h2>
      <p>地图随机生成了 ${currentLayer.length} 个可选节点。精英风险更高，但更容易提供高价值 Mutation。</p>
      <div class="decision-rules">
        <div><span>公开节点</span><strong>完整评估反馈</strong></div>
        <div><span>精英节点</span><strong>更高难度与奖励</strong></div>
        <div><span>Hidden Boss</span><strong>隔离数据，不提供训练反馈</strong></div>
      </div>
      <p class="select-hint">← 在地图中选择高亮节点</p>
    </div>
  `;
}

function renderRewardPanel() {
  const node = getSelectedNode(run);
  const isLab = run.lastResult?.kind === "lab";

  return `
    <div class="reward-content">
      <span class="encounter-kicker">${isLab ? "LAB MUTATION" : "ENCOUNTER FEEDBACK"}</span>
      ${renderResult(run.lastResult)}
      <div class="reward-heading">
        <div><h2>选择一个 Mutation</h2><p>${
          isLab
            ? "实验室根据当前目标生成了三个构筑方向。"
            : `针对「${getMonsterById(node?.monsterId)?.failureMode ?? "当前场景"}」生成，但保留探索性选项。`
        }</p></div>
        <span>1 / ${run.currentDraft.length}</span>
      </div>
      <div class="mutation-draft">
        ${
          run.currentDraft.length
            ? run.currentDraft.map(renderMutationCard).join("")
            : `<p class="empty-copy">当前 Complexity 无法容纳新的 Mutation。</p>`
        }
      </div>
      <button class="text-button" data-action="skip-mutation">放弃奖励，保持当前构筑 →</button>
    </div>
  `;
}

function renderEndPanel() {
  const victory = run.status === "victory";
  const passed = run.encounterHistory.filter((item) => item.passed).length;
  const total = run.encounterHistory.length;

  return `
    <div class="action-content end-content ${victory ? "victory" : "defeat"}">
      <span class="encounter-kicker">RUN ${victory ? "COMPLETE" : "TERMINATED"}</span>
      <div class="end-symbol">${victory ? "✦" : "×"}</div>
      <h2>${victory ? "获得候选发布资格" : "进化分支已经死亡"}</h2>
      <p>${
        victory
          ? "Skill 已通过隔离的端到端隐藏验收。下一步应进入安全检查和 Canary，而不是直接覆盖生产版本。"
          : "生产 Skill 没有受到影响。地图、选择、评估与失败样本已经保存在本次 Replay 中。"
      }</p>
      <div class="run-summary">
        <div><span>遭遇通过</span><strong>${passed} / ${total}</strong></div>
        <div><span>Mutation</span><strong>${run.mutationIds.length}</strong></div>
        <div><span>武器进化</span><strong>${run.evolutionIds.length}</strong></div>
        <div><span>最终得分</span><strong>${calculateObjectiveScore(run)}</strong></div>
      </div>
      <button class="primary-button" data-action="retry-seed">使用相同 Seed 重新构筑</button>
      <button class="text-button" data-action="return-setup">返回 Run 设置</button>
    </div>
  `;
}

function renderActionPanel() {
  let content = renderChoosePrompt();
  if (run.phase === "encounter") content = renderEncounterPanel();
  if (run.phase === "reward") content = renderRewardPanel();
  if (run.phase === "ended") content = renderEndPanel();

  return `<aside class="panel action-panel">${content}</aside>`;
}

function renderRunLog() {
  return `
    <section class="panel log-panel">
      <div class="log-heading">
        <div><span>RUN REPLAY</span><h2>进化记录</h2></div>
        <span>${run.logs.length} EVENTS</span>
      </div>
      <div class="log-list">
        ${[...run.logs]
          .reverse()
          .map(
            (entry) => `
              <div class="log-entry ${entry.tone}">
                <span>${String(entry.id).padStart(2, "0")}</span>
                <i></i>
                <p>${escapeHtml(entry.message)}</p>
                <small>ACT ${entry.act}</small>
              </div>`,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderRun() {
  document.title = `RogueSkills · ${run.seed} · Act ${run.actIndex + 1}`;
  const mode = RUN_MODES[run.modeId];

  root.innerHTML = `
    <main class="run-shell">
      <header class="run-nav">
        <a class="brand" href="#" aria-label="RogueSkills">
          <span class="brand-mark">R</span>
          <span><strong>RogueSkills</strong><small>EVOLUTION RUN</small></span>
        </a>
        <div class="run-identity">
          <span>${escapeHtml(run.skillName ?? ARCHETYPES[run.archetypeId].name)}</span>
          <i></i>
          <span>${mode.name}</span>
          <i></i>
          <code>${escapeHtml(run.seed)}</code>
        </div>
        <div class="nav-actions">
          <a class="discovery-link" href="./discovery.html">Skill Discovery</a>
          <button class="nav-button" data-action="return-setup">新建 Run</button>
        </div>
      </header>
      ${renderHud()}
      <div class="game-grid">
        ${renderBuildPanel()}
        ${renderMap()}
        ${renderActionPanel()}
      </div>
      ${renderRunLog()}
      <footer class="run-footer">
        <span>BENCHMARK RUNNER · SAVE V${SAVE_VERSION}</span>
        <span>刷新页面可恢复当前 Run</span>
      </footer>
    </main>
  `;
}

function render() {
  if (run) renderRun();
  else renderSetup();
}

root.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-action]");
  if (!trigger) return;

  const action = trigger.dataset.action;

  if (action === "random-seed") {
    const input = document.querySelector("#run-seed");
    if (input) input.value = makeSeed();
    return;
  }

  if (action === "start-run") {
    const seed = document.querySelector("#run-seed")?.value;
    const modeId = document.querySelector('input[name="mode"]:checked')?.value;
    const selectedSkill = initialSkills.find((skill) => skill.id === selectedInitialSkillId) ?? initialSkills[0];
    run = createRun({ seed, modeId, skillGenome: selectedSkill?.genome ?? null });
    persistRun();
    render();
    return;
  }

  if (action === "select-base-skill") {
    selectedInitialSkillId = trigger.dataset.skillId;
    render();
    return;
  }

  if (action === "continue-run" && savedRun) {
    run = savedRun;
    render();
    return;
  }

  if (action === "return-setup") {
    run = null;
    render();
    return;
  }

  if (action === "retry-seed") {
    run = createRun({
      seed: run.seed,
      archetypeId: run.archetypeId,
      modeId: run.modeId,
      skillGenome: run.baseSkillGenome,
    });
    persistRun();
    render();
    return;
  }

  if (action === "select-node") {
    run = selectNode(run, trigger.dataset.nodeId);
  }

  if (action === "resolve-node") {
    run = resolveCurrentNode(run);
  }

  if (action === "choose-mutation") {
    run = chooseMutation(run, trigger.dataset.mutationId);
  }

  if (action === "skip-mutation") {
    run = skipMutation(run);
  }

  persistRun();
  render();
});

render();
listInitialSkills()
  .then(({ skills }) => {
    initialSkills = skills;
    initialLibraryState = "ready";
    if (!selectedInitialSkillId && skills.length) selectedInitialSkillId = skills[0].id;
    if (!run) render();
  })
  .catch(() => {
    initialLibraryState = "offline";
    if (!run) render();
  });
