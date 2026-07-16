from copy import deepcopy
from math import floor
from typing import Any

from .benchmark import run_scenario_benchmark
from .catalogs import (
    ARCHETYPES,
    EVOLUTIONS,
    MONSTERS,
    MUTATIONS,
    NODE_TYPES,
    REGIONS,
    RUN_MODES,
    STAT_LABELS,
)
from .genome import capability_profile_from_genome
from .shared import clamp, create_rng, hash_string, pick, round_number, shuffle

MAX_STABILITY = 12
MAX_COMPLEXITY = 8
SAVE_VERSION = 2
BASE_DIFFICULTY = [42, 50, 57]


def _mutation(mutation_id: str) -> dict[str, Any] | None:
    return next((item for item in MUTATIONS if item["id"] == mutation_id), None)


def _log_entry(state: dict[str, Any], message: str, tone: str = "info") -> dict[str, Any]:
    return {
        "id": len(state["logs"]) + 1,
        "act": state["actIndex"] + 1,
        "message": message,
        "tone": tone,
    }


def _with_log(state: dict[str, Any], message: str, tone: str = "info") -> dict[str, Any]:
    next_state = deepcopy(state)
    next_state["logs"].append(_log_entry(state, message, tone))
    return next_state


def _create_node(
    *,
    seed: str,
    region: dict[str, Any],
    act_index: int,
    layer_index: int,
    option_index: int,
    node_type: str,
    monster_id: str | None,
) -> dict[str, Any]:
    random = create_rng(f"{seed}|node|{act_index}|{layer_index}|{option_index}")
    type_bonus = 5 if node_type == "elite" else 7 if node_type == "boss" else 0
    layer_bonus = min(layer_index, 3)
    jitter = floor(random() * 5) - 2
    return {
        "id": f"a{act_index + 1}-l{layer_index + 1}-n{option_index + 1}",
        "act": act_index + 1,
        "layer": layer_index,
        "regionId": region["id"],
        "type": node_type,
        "monsterId": monster_id,
        "difficulty": BASE_DIFFICULTY[act_index] + type_bonus + layer_bonus + jitter,
        "rewardTier": "uncommon" if node_type in ("elite", "lab") else "common",
    }


def generate_map(seed: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for act_index, source_region in enumerate(REGIONS):
        region = deepcopy(source_region)
        random = create_rng(f"{seed}|map|act-{act_index + 1}")
        monster_order = shuffle(region["monsters"], random)
        utility_pattern = pick(
            [["lab", "normal"], ["rest", "elite"], ["lab", "rest"], ["normal", "elite"]],
            random,
        )
        patterns = [["normal", "normal"], ["normal", "elite"], utility_pattern, ["boss"]]
        monster_cursor = 0
        layers: list[list[dict[str, Any]]] = []
        for layer_index, pattern in enumerate(patterns):
            layer = []
            for option_index, node_type in enumerate(pattern):
                is_combat = node_type in ("normal", "elite")
                if node_type == "boss":
                    monster_id = region["boss"]
                elif is_combat:
                    monster_id = monster_order[monster_cursor % len(monster_order)]
                    monster_cursor += 1
                else:
                    monster_id = None
                layer.append(
                    _create_node(
                        seed=seed,
                        region=region,
                        act_index=act_index,
                        layer_index=layer_index,
                        option_index=option_index,
                        node_type=node_type,
                        monster_id=monster_id,
                    )
                )
            layers.append(layer)
        region["layers"] = layers
        result.append(region)
    return result


def create_run(
    *,
    seed: str,
    archetype_id: str = "browser",
    mode_id: str = "stable",
    skill_genome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_seed = str(seed or "ROGUE-001").strip() or "ROGUE-001"
    archetype = ARCHETYPES.get(archetype_id, ARCHETYPES["browser"])
    mode = RUN_MODES.get(mode_id, RUN_MODES["stable"])
    skill_name = skill_genome.get("name", archetype["name"]) if skill_genome else archetype["name"]
    skill_role = (
        skill_genome.get("metadata", {}).get("category", archetype["role"])
        if skill_genome
        else archetype["role"]
    )
    skill_description = (
        skill_genome.get("description", archetype["description"])
        if skill_genome
        else archetype["description"]
    )
    initial_weapons = (
        skill_genome.get("tools", [])[:5]
        if skill_genome and skill_genome.get("tools")
        else deepcopy(archetype["initialWeapons"])
    )
    initial_stats = (
        capability_profile_from_genome(skill_genome)
        if skill_genome
        else deepcopy(archetype["stats"])
    )
    run_hash_input = f"{normalized_seed}|{archetype['id']}|{mode['id']}"
    run = {
        "saveVersion": SAVE_VERSION,
        "id": f"run-{hash_string(run_hash_input):x}",
        "seed": normalized_seed,
        "archetypeId": archetype["id"],
        "baseSkillId": skill_genome.get("id", archetype["id"]) if skill_genome else archetype["id"],
        "baseSkillVersion": skill_genome.get("schemaVersion") if skill_genome else None,
        "baseSkillGenome": deepcopy(skill_genome),
        "skillName": skill_name,
        "skillRole": skill_role,
        "skillDescription": skill_description,
        "modeId": mode["id"],
        "status": "active",
        "phase": "choose_node",
        "actIndex": 0,
        "layerIndex": 0,
        "selectedNodeId": None,
        "stability": MAX_STABILITY,
        "compute": 100,
        "complexityUsed": 0,
        "complexityMax": MAX_COMPLEXITY,
        "stats": initial_stats,
        "initialWeapons": initial_weapons,
        "mutationIds": [],
        "evolutionIds": [],
        "map": generate_map(normalized_seed),
        "completedNodeIds": [],
        "encounterHistory": [],
        "currentDraft": [],
        "lastResult": None,
        "logs": [],
    }
    return _with_log(
        run, f"以 {skill_name} 进入「{mode['name']}」Run，地图 Seed：{normalized_seed}。", "accent"
    )


def get_current_region(state: dict[str, Any]) -> dict[str, Any] | None:
    return state["map"][state["actIndex"]] if state["actIndex"] < len(state["map"]) else None


def get_current_layer(state: dict[str, Any]) -> list[dict[str, Any]]:
    region = get_current_region(state)
    if not region or state["layerIndex"] >= len(region["layers"]):
        return []
    return region["layers"][state["layerIndex"]]


def get_selected_node(state: dict[str, Any]) -> dict[str, Any] | None:
    if not state.get("selectedNodeId"):
        return None
    region = get_current_region(state)
    if not region:
        return None
    return next(
        (
            node
            for layer in region["layers"]
            for node in layer
            if node["id"] == state["selectedNodeId"]
        ),
        None,
    )


def get_tag_counts(state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mutation_id in state["mutationIds"]:
        mutation = _mutation(mutation_id)
        if mutation:
            for tag in mutation["tags"]:
                counts[tag] = counts.get(tag, 0) + 1
    return counts


def get_evolution_progress(state: dict[str, Any]) -> list[dict[str, Any]]:
    tags = get_tag_counts(state)
    result = []
    for source in EVOLUTIONS:
        evolution = deepcopy(source)
        requirements = [
            {"tag": tag, "required": required, "current": min(tags.get(tag, 0), required)}
            for tag, required in evolution["tagRequirements"].items()
        ]
        evolution.update(
            {
                "unlocked": evolution["id"] in state["evolutionIds"],
                "requirements": requirements,
                "progress": sum(item["current"] for item in requirements),
                "total": sum(item["required"] for item in requirements),
            }
        )
        result.append(evolution)
    return result


def select_node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    if state["status"] != "active" or state["phase"] != "choose_node":
        return deepcopy(state)
    node = next((item for item in get_current_layer(state) if item["id"] == node_id), None)
    if not node:
        return deepcopy(state)
    monster = MONSTERS.get(node["monsterId"]) if node.get("monsterId") else None
    label = (
        f"{monster['name']} · {monster['failureMode']}"
        if monster
        else "进化实验室"
        if node["type"] == "lab"
        else "安全节点"
    )
    next_state = deepcopy(state)
    next_state.update(
        {"phase": "encounter", "selectedNodeId": node["id"], "currentDraft": [], "lastResult": None}
    )
    return _with_log(next_state, f"选择路线：{label}。")


def evaluate_encounter(
    state: dict[str, Any], node: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    node = node or get_selected_node(state)
    if not node or not node.get("monsterId"):
        return None
    monster = MONSTERS[node["monsterId"]]
    result = run_scenario_benchmark(
        profile=state["stats"],
        scenario=monster,
        difficulty=node["difficulty"],
        node_type=node["type"],
        compute_available=state["compute"],
        objective_score=calculate_objective_score(state),
    )
    return {**result, "nodeId": node["id"], "monsterId": monster["id"]}


def calculate_objective_score(state: dict[str, Any]) -> float:
    weights = RUN_MODES[state["modeId"]]["weights"]
    return round_number(
        sum(state["stats"].get(stat, 0) * weight for stat, weight in weights.items()), 1
    )


def _mutation_relevance(
    mutation: dict[str, Any], state: dict[str, Any], monster: dict[str, Any] | None, random: Any
) -> float:
    encounter_gain = (
        sum(
            max(0, mutation["effects"].get(stat, 0)) * weight
            for stat, weight in monster["requirements"].items()
        )
        if monster
        else 0
    )
    mode_gain = sum(
        max(0, mutation["effects"].get(stat, 0)) * weight
        for stat, weight in RUN_MODES[state["modeId"]]["weights"].items()
    )
    rarity_boost = (
        2 if mutation["rarity"] == "rare" else 1 if mutation["rarity"] == "uncommon" else 0
    )
    return encounter_gain * 1.5 + mode_gain + rarity_boost + random() * 12


def create_mutation_draft(state: dict[str, Any], node: dict[str, Any] | None = None) -> list[str]:
    node = node or get_selected_node(state)
    monster = MONSTERS.get(node["monsterId"]) if node and node.get("monsterId") else None
    random = create_rng(
        f"{state['seed']}|draft|{node['id'] if node else 'free'}|{','.join(state['mutationIds'])}|{state['modeId']}"
    )
    remaining = state["complexityMax"] - state["complexityUsed"]
    available = [
        item
        for item in MUTATIONS
        if item["id"] not in state["mutationIds"] and item["complexityCost"] <= remaining
    ]
    scored = sorted(
        (
            {"mutation": item, "score": _mutation_relevance(item, state, monster, random)}
            for item in shuffle(available, random)
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    if len(scored) <= 3:
        return [item["mutation"]["id"] for item in scored]
    first = scored[0]
    middle_pool = scored[1 : min(7, len(scored))]
    second = pick(middle_pool, random)
    rest = [item for item in scored if item is not first and item is not second]
    third = pick(rest, random)
    return [first["mutation"]["id"], second["mutation"]["id"], third["mutation"]["id"]]


def _complete_selected_node(state: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state)
    if state.get("selectedNodeId") and state["selectedNodeId"] not in state["completedNodeIds"]:
        next_state["completedNodeIds"].append(state["selectedNodeId"])
    return next_state


def _advance_layer(state: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state)
    next_state.update(
        {
            "phase": "choose_node",
            "layerIndex": state["layerIndex"] + 1,
            "selectedNodeId": None,
            "currentDraft": [],
        }
    )
    return next_state


def _resolve_rest_node(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    healed = min(3, MAX_STABILITY - state["stability"])
    next_state = deepcopy(state)
    next_state.update(
        {
            "stability": state["stability"] + healed,
            "compute": state["compute"] + 10,
            "lastResult": {
                "nodeId": node["id"],
                "kind": "rest",
                "healed": healed,
                "computeReward": 10,
            },
        }
    )
    next_state = _advance_layer(_complete_selected_node(next_state))
    return _with_log(next_state, f"在安全节点重整：Stability +{healed}，Compute +10。", "success")


def _resolve_lab_node(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    next_state = _complete_selected_node(state)
    next_state.update(
        {
            "phase": "reward",
            "currentDraft": create_mutation_draft(state, node),
            "lastResult": {"nodeId": node["id"], "kind": "lab"},
        }
    )
    return _with_log(next_state, "进入进化实验室：获得一次无战斗 Mutation Draft。", "accent")


def _resolve_boss(
    state: dict[str, Any], node: dict[str, Any], result: dict[str, Any], settled: dict[str, Any]
) -> dict[str, Any]:
    next_state = deepcopy(settled)
    if not result["passed"]:
        next_state.update({"status": "defeat", "phase": "ended", "currentDraft": []})
        return _with_log(
            next_state,
            f"{MONSTERS[node['monsterId']]['name']} 的隐藏验收未通过，本次候选分支终止。",
            "danger",
        )
    if state["actIndex"] == len(state["map"]) - 1:
        next_state.update({"status": "victory", "phase": "ended", "currentDraft": []})
        return _with_log(next_state, "最终隐藏验收通过：该 Skill 获得候选发布资格。", "success")
    next_region = state["map"][state["actIndex"] + 1]
    next_state.update(
        {
            "actIndex": state["actIndex"] + 1,
            "layerIndex": 0,
            "phase": "choose_node",
            "selectedNodeId": None,
            "currentDraft": [],
        }
    )
    return _with_log(
        next_state,
        f"Boss 通过，进入第 {state['actIndex'] + 2} 幕「{next_region['name']}」。",
        "success",
    )


def resolve_current_node(state: dict[str, Any]) -> dict[str, Any]:
    if state["status"] != "active" or state["phase"] != "encounter":
        return deepcopy(state)
    node = get_selected_node(state)
    if not node:
        return deepcopy(state)
    if node["type"] == "rest":
        return _resolve_rest_node(state, node)
    if node["type"] == "lab":
        return _resolve_lab_node(state, node)
    result = evaluate_encounter(state, node)
    assert result is not None
    next_stability = max(0, state["stability"] - result["stabilityDamage"])
    next_compute = max(0, state["compute"] - result["computeCost"] + result["computeReward"])
    settled = deepcopy(state)
    settled.update({"stability": next_stability, "compute": next_compute, "lastResult": result})
    settled["encounterHistory"].append(result)
    settled = _complete_selected_node(settled)
    monster = MONSTERS[node["monsterId"]]
    outcome = "通过" if result["passed"] else f"失败，Stability -{result['stabilityDamage']}"
    settled = _with_log(
        settled,
        f"{monster['name']}：Coverage {result['coverage']}% / {result['threshold']}%，{outcome}。",
        "success" if result["passed"] else "danger",
    )
    if node["type"] == "boss":
        return _resolve_boss(state, node, result, settled)
    if next_stability <= 0:
        settled.update({"status": "defeat", "phase": "ended", "currentDraft": []})
        return _with_log(
            settled, "Stability 已归零，本次进化分支死亡；Replay 与失败知识已保留。", "danger"
        )
    settled.update({"phase": "reward", "currentDraft": create_mutation_draft(settled, node)})
    return settled


def _apply_effects(stats: dict[str, float], effects: dict[str, float]) -> dict[str, float]:
    next_stats = deepcopy(stats)
    for stat, value in effects.items():
        next_stats[stat] = clamp(next_stats.get(stat, 0) + value, 0, 100)
    return next_stats


def _unlock_evolutions(state: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state)
    for evolution in get_evolution_progress(next_state):
        if not evolution["unlocked"] and all(
            item["current"] >= item["required"] for item in evolution["requirements"]
        ):
            next_state["stats"] = _apply_effects(next_state["stats"], evolution["effects"])
            next_state["evolutionIds"].append(evolution["id"])
            next_state = _with_log(
                next_state, f"武器进化：{evolution['name']} 已形成。", "evolution"
            )
    return next_state


def choose_mutation(state: dict[str, Any], mutation_id: str) -> dict[str, Any]:
    if (
        state["status"] != "active"
        or state["phase"] != "reward"
        or mutation_id not in state["currentDraft"]
    ):
        return deepcopy(state)
    mutation = _mutation(mutation_id)
    if (
        not mutation
        or mutation["id"] in state["mutationIds"]
        or state["complexityUsed"] + mutation["complexityCost"] > state["complexityMax"]
    ):
        return deepcopy(state)
    next_state = deepcopy(state)
    next_state["stats"] = _apply_effects(state["stats"], mutation["effects"])
    next_state["mutationIds"].append(mutation["id"])
    next_state["complexityUsed"] += mutation["complexityCost"]
    next_state = _with_log(
        next_state, f"选择 Mutation「{mutation['name']}」：{mutation['benefit']}", "accent"
    )
    return _advance_layer(_unlock_evolutions(next_state))


def skip_mutation(state: dict[str, Any]) -> dict[str, Any]:
    if state["status"] != "active" or state["phase"] != "reward":
        return deepcopy(state)
    return _advance_layer(_with_log(state, "放弃本次 Mutation，保持当前构筑。"))


def get_mutation_by_id(mutation_id: str) -> dict[str, Any] | None:
    mutation = _mutation(mutation_id)
    return deepcopy(mutation) if mutation else None


def get_evolution_by_id(evolution_id: str) -> dict[str, Any] | None:
    evolution = next((item for item in EVOLUTIONS if item["id"] == evolution_id), None)
    return deepcopy(evolution) if evolution else None


def get_monster_by_id(monster_id: str) -> dict[str, Any] | None:
    monster = MONSTERS.get(monster_id)
    return deepcopy(monster) if monster else None


def public_catalog() -> dict[str, Any]:
    return {
        "archetypes": ARCHETYPES,
        "evolutions": EVOLUTIONS,
        "monsters": MONSTERS,
        "mutations": MUTATIONS,
        "nodeTypes": NODE_TYPES,
        "runModes": RUN_MODES,
        "statLabels": STAT_LABELS,
    }
