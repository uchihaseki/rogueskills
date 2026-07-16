// Frozen JS parity oracle. Do not import from the browser or production backend.
import {
  ARCHETYPES,
  EVOLUTIONS,
  MONSTERS,
  MUTATIONS,
  REGIONS,
  RUN_MODES,
} from "./catalog.js";
import { runScenarioBenchmark } from "../benchmark/runner.js";
import { clamp, createRng, hashString, pick, round, shuffle } from "../shared/random.js";
import { capabilityProfileFromGenome } from "../genome/skill-genome.js";

export const MAX_STABILITY = 12;
export const MAX_COMPLEXITY = 8;
export const SAVE_VERSION = 1;

const BASE_DIFFICULTY = [42, 50, 57];

function logEntry(state, message, tone = "info") {
  return {
    id: state.logs.length + 1,
    act: state.actIndex + 1,
    message,
    tone,
  };
}

function withLog(state, message, tone = "info") {
  return {
    ...state,
    logs: [...state.logs, logEntry(state, message, tone)],
  };
}

function createNode({ seed, region, actIndex, layerIndex, optionIndex, type, monsterId }) {
  const random = createRng(`${seed}|node|${actIndex}|${layerIndex}|${optionIndex}`);
  const typeBonus = type === "elite" ? 5 : type === "boss" ? 7 : 0;
  const layerBonus = Math.min(layerIndex, 3);
  const jitter = Math.floor(random() * 5) - 2;

  return {
    id: `a${actIndex + 1}-l${layerIndex + 1}-n${optionIndex + 1}`,
    act: actIndex + 1,
    layer: layerIndex,
    regionId: region.id,
    type,
    monsterId,
    difficulty: BASE_DIFFICULTY[actIndex] + typeBonus + layerBonus + jitter,
    rewardTier: type === "elite" || type === "lab" ? "uncommon" : "common",
  };
}

export function generateMap(seed) {
  return REGIONS.map((region, actIndex) => {
    const random = createRng(`${seed}|map|act-${actIndex + 1}`);
    const monsterOrder = shuffle(region.monsters, random);
    const utilityPattern = pick(
      [
        ["lab", "normal"],
        ["rest", "elite"],
        ["lab", "rest"],
        ["normal", "elite"],
      ],
      random,
    );
    const patterns = [
      ["normal", "normal"],
      ["normal", "elite"],
      utilityPattern,
      ["boss"],
    ];
    let monsterCursor = 0;

    const layers = patterns.map((pattern, layerIndex) =>
      pattern.map((type, optionIndex) => {
        const isCombat = type === "normal" || type === "elite";
        const monsterId =
          type === "boss"
            ? region.boss
            : isCombat
              ? monsterOrder[monsterCursor++ % monsterOrder.length]
              : null;

        return createNode({
          seed,
          region,
          actIndex,
          layerIndex,
          optionIndex,
          type,
          monsterId,
        });
      }),
    );

    return { ...region, layers };
  });
}

export function createRun({ seed, archetypeId = "browser", modeId = "stable", skillGenome = null }) {
  const normalizedSeed = String(seed || "ROGUE-001").trim() || "ROGUE-001";
  const archetype = ARCHETYPES[archetypeId] ?? ARCHETYPES.browser;
  const mode = RUN_MODES[modeId] ?? RUN_MODES.stable;
  const skillName = skillGenome?.name ?? archetype.name;
  const skillRole = skillGenome?.metadata?.category ?? archetype.role;
  const skillDescription = skillGenome?.description ?? archetype.description;
  const initialWeapons = skillGenome?.tools?.length
    ? skillGenome.tools.slice(0, 5)
    : [...archetype.initialWeapons];
  const initialStats = skillGenome ? capabilityProfileFromGenome(skillGenome) : { ...archetype.stats };
  const run = {
    saveVersion: SAVE_VERSION,
    id: `run-${hashString(`${normalizedSeed}|${archetype.id}|${mode.id}`).toString(16)}`,
    seed: normalizedSeed,
    archetypeId: archetype.id,
    baseSkillId: skillGenome?.id ?? archetype.id,
    baseSkillVersion: skillGenome?.schemaVersion ?? null,
    baseSkillGenome: skillGenome ?? null,
    skillName,
    skillRole,
    skillDescription,
    modeId: mode.id,
    status: "active",
    phase: "choose_node",
    actIndex: 0,
    layerIndex: 0,
    selectedNodeId: null,
    stability: MAX_STABILITY,
    compute: 100,
    complexityUsed: 0,
    complexityMax: MAX_COMPLEXITY,
    stats: initialStats,
    initialWeapons,
    mutationIds: [],
    evolutionIds: [],
    map: generateMap(normalizedSeed),
    completedNodeIds: [],
    encounterHistory: [],
    currentDraft: [],
    lastResult: null,
    logs: [],
  };

  return withLog(
    run,
    `以 ${skillName} 进入「${mode.name}」Run，地图 Seed：${normalizedSeed}。`,
    "accent",
  );
}

export function getCurrentRegion(state) {
  return state.map[state.actIndex] ?? null;
}

export function getCurrentLayer(state) {
  return getCurrentRegion(state)?.layers[state.layerIndex] ?? [];
}

export function getSelectedNode(state) {
  if (!state.selectedNodeId) return null;
  return getCurrentRegion(state)?.layers.flat().find((node) => node.id === state.selectedNodeId) ?? null;
}

export function getTagCounts(state) {
  const counts = {};

  for (const mutationId of state.mutationIds) {
    const mutation = MUTATIONS.find((item) => item.id === mutationId);
    if (!mutation) continue;

    for (const tag of mutation.tags) {
      counts[tag] = (counts[tag] ?? 0) + 1;
    }
  }

  return counts;
}

export function getEvolutionProgress(state) {
  const tags = getTagCounts(state);

  return EVOLUTIONS.map((evolution) => {
    const requirements = Object.entries(evolution.tagRequirements).map(([tag, required]) => ({
      tag,
      required,
      current: Math.min(tags[tag] ?? 0, required),
    }));
    const progress = requirements.reduce((total, item) => total + item.current, 0);
    const total = requirements.reduce((sum, item) => sum + item.required, 0);

    return {
      ...evolution,
      unlocked: state.evolutionIds.includes(evolution.id),
      requirements,
      progress,
      total,
    };
  });
}

export function selectNode(state, nodeId) {
  if (state.status !== "active" || state.phase !== "choose_node") return state;

  const node = getCurrentLayer(state).find((item) => item.id === nodeId);
  if (!node) return state;

  const monster = node.monsterId ? MONSTERS[node.monsterId] : null;
  const label = monster ? `${monster.name} · ${monster.failureMode}` : node.type === "lab" ? "进化实验室" : "安全节点";

  return withLog(
    {
      ...state,
      phase: "encounter",
      selectedNodeId: node.id,
      currentDraft: [],
      lastResult: null,
    },
    `选择路线：${label}。`,
  );
}

export function evaluateEncounter(state, node = getSelectedNode(state)) {
  if (!node?.monsterId) return null;

  const monster = MONSTERS[node.monsterId];
  return {
    ...runScenarioBenchmark({
      profile: state.stats,
      scenario: monster,
      difficulty: node.difficulty,
      nodeType: node.type,
      computeAvailable: state.compute,
      objectiveScore: calculateObjectiveScore(state),
    }),
    nodeId: node.id,
    monsterId: monster.id,
  };
}

export function calculateObjectiveScore(state) {
  const mode = RUN_MODES[state.modeId];
  return round(
    Object.entries(mode.weights).reduce(
      (total, [stat, weight]) => total + (state.stats[stat] ?? 0) * weight,
      0,
    ),
    1,
  );
}

function mutationRelevance(mutation, state, monster, random) {
  const encounterGain = monster
    ? Object.entries(monster.requirements).reduce(
        (total, [stat, weight]) => total + Math.max(0, mutation.effects[stat] ?? 0) * weight,
        0,
      )
    : 0;
  const mode = RUN_MODES[state.modeId];
  const modeGain = Object.entries(mode.weights).reduce(
    (total, [stat, weight]) => total + Math.max(0, mutation.effects[stat] ?? 0) * weight,
    0,
  );
  const rarityBoost = mutation.rarity === "rare" ? 2 : mutation.rarity === "uncommon" ? 1 : 0;

  return encounterGain * 1.5 + modeGain + rarityBoost + random() * 12;
}

export function createMutationDraft(state, node = getSelectedNode(state)) {
  const monster = node?.monsterId ? MONSTERS[node.monsterId] : null;
  const random = createRng(
    `${state.seed}|draft|${node?.id ?? "free"}|${state.mutationIds.join(",")}|${state.modeId}`,
  );
  const remainingComplexity = state.complexityMax - state.complexityUsed;
  const available = MUTATIONS.filter(
    (mutation) =>
      !state.mutationIds.includes(mutation.id) && mutation.complexityCost <= remainingComplexity,
  );
  const scored = shuffle(available, random)
    .map((mutation) => ({
      mutation,
      score: mutationRelevance(mutation, state, monster, random),
    }))
    .sort((left, right) => right.score - left.score);

  if (scored.length <= 3) return scored.map((item) => item.mutation.id);

  const first = scored[0];
  const middlePool = scored.slice(1, Math.min(7, scored.length));
  const second = pick(middlePool, random);
  const rest = scored.filter((item) => item !== first && item !== second);
  const third = pick(rest, random);

  return [first.mutation.id, second.mutation.id, third.mutation.id];
}

function completeSelectedNode(state) {
  if (!state.selectedNodeId || state.completedNodeIds.includes(state.selectedNodeId)) return state;
  return {
    ...state,
    completedNodeIds: [...state.completedNodeIds, state.selectedNodeId],
  };
}

function advanceLayer(state) {
  return {
    ...state,
    phase: "choose_node",
    layerIndex: state.layerIndex + 1,
    selectedNodeId: null,
    currentDraft: [],
  };
}

function resolveRestNode(state, node) {
  const healed = Math.min(3, MAX_STABILITY - state.stability);
  const next = advanceLayer(
    completeSelectedNode({
      ...state,
      stability: state.stability + healed,
      compute: state.compute + 10,
      lastResult: {
        nodeId: node.id,
        kind: "rest",
        healed,
        computeReward: 10,
      },
    }),
  );

  return withLog(next, `在安全节点重整：Stability +${healed}，Compute +10。`, "success");
}

function resolveLabNode(state, node) {
  const draft = createMutationDraft(state, node);
  const next = completeSelectedNode({
    ...state,
    phase: "reward",
    currentDraft: draft,
    lastResult: { nodeId: node.id, kind: "lab" },
  });

  return withLog(next, "进入进化实验室：获得一次无战斗 Mutation Draft。", "accent");
}

function resolveBoss(state, node, result, settled) {
  if (!result.passed) {
    return withLog(
      {
        ...settled,
        status: "defeat",
        phase: "ended",
        currentDraft: [],
      },
      `${MONSTERS[node.monsterId].name} 的隐藏验收未通过，本次候选分支终止。`,
      "danger",
    );
  }

  if (state.actIndex === state.map.length - 1) {
    return withLog(
      {
        ...settled,
        status: "victory",
        phase: "ended",
        currentDraft: [],
      },
      "最终隐藏验收通过：该 Skill 获得候选发布资格。",
      "success",
    );
  }

  const nextRegion = state.map[state.actIndex + 1];
  return withLog(
    {
      ...settled,
      actIndex: state.actIndex + 1,
      layerIndex: 0,
      phase: "choose_node",
      selectedNodeId: null,
      currentDraft: [],
    },
    `Boss 通过，进入第 ${state.actIndex + 2} 幕「${nextRegion.name}」。`,
    "success",
  );
}

export function resolveCurrentNode(state) {
  if (state.status !== "active" || state.phase !== "encounter") return state;

  const node = getSelectedNode(state);
  if (!node) return state;
  if (node.type === "rest") return resolveRestNode(state, node);
  if (node.type === "lab") return resolveLabNode(state, node);

  const result = evaluateEncounter(state, node);
  const nextStability = Math.max(0, state.stability - result.stabilityDamage);
  const nextCompute = Math.max(0, state.compute - result.computeCost + result.computeReward);
  let settled = completeSelectedNode({
    ...state,
    stability: nextStability,
    compute: nextCompute,
    lastResult: result,
    encounterHistory: [...state.encounterHistory, result],
  });
  const monster = MONSTERS[node.monsterId];

  settled = withLog(
    settled,
    `${monster.name}：Coverage ${result.coverage}% / ${result.threshold}%，${
      result.passed ? "通过" : `失败，Stability -${result.stabilityDamage}`
    }。`,
    result.passed ? "success" : "danger",
  );

  if (node.type === "boss") return resolveBoss(state, node, result, settled);

  if (nextStability <= 0) {
    return withLog(
      { ...settled, status: "defeat", phase: "ended", currentDraft: [] },
      "Stability 已归零，本次进化分支死亡；Replay 与失败知识已保留。",
      "danger",
    );
  }

  const draft = createMutationDraft(settled, node);
  return {
    ...settled,
    phase: "reward",
    currentDraft: draft,
  };
}

function applyEffects(stats, effects) {
  const next = { ...stats };

  for (const [stat, value] of Object.entries(effects)) {
    next[stat] = clamp((next[stat] ?? 0) + value, 0, 100);
  }

  return next;
}

function unlockEvolutions(state) {
  const progress = getEvolutionProgress(state);
  const newlyUnlocked = progress.filter(
    (evolution) =>
      !evolution.unlocked && evolution.requirements.every((item) => item.current >= item.required),
  );
  let next = state;

  for (const evolution of newlyUnlocked) {
    next = withLog(
      {
        ...next,
        stats: applyEffects(next.stats, evolution.effects),
        evolutionIds: [...next.evolutionIds, evolution.id],
      },
      `武器进化：${evolution.name} 已形成。`,
      "evolution",
    );
  }

  return next;
}

export function chooseMutation(state, mutationId) {
  if (state.status !== "active" || state.phase !== "reward") return state;
  if (!state.currentDraft.includes(mutationId)) return state;

  const mutation = MUTATIONS.find((item) => item.id === mutationId);
  if (!mutation || state.mutationIds.includes(mutation.id)) return state;
  if (state.complexityUsed + mutation.complexityCost > state.complexityMax) return state;

  let next = withLog(
    {
      ...state,
      stats: applyEffects(state.stats, mutation.effects),
      mutationIds: [...state.mutationIds, mutation.id],
      complexityUsed: state.complexityUsed + mutation.complexityCost,
    },
    `选择 Mutation「${mutation.name}」：${mutation.benefit}`,
    "accent",
  );

  next = unlockEvolutions(next);
  return advanceLayer(next);
}

export function skipMutation(state) {
  if (state.status !== "active" || state.phase !== "reward") return state;
  return advanceLayer(withLog(state, "放弃本次 Mutation，保持当前构筑。"));
}

export function getMutationById(id) {
  return MUTATIONS.find((mutation) => mutation.id === id) ?? null;
}

export function getEvolutionById(id) {
  return EVOLUTIONS.find((evolution) => evolution.id === id) ?? null;
}

export function getMonsterById(id) {
  return MONSTERS[id] ?? null;
}
