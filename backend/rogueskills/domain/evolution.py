from copy import deepcopy
from math import floor
from typing import Any

from .benchmark import run_scenario_benchmark
from .catalogs import (
    ARCHETYPES,
    EVOLUTIONS,
    FINANCE_REGIONS,
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
SAVE_VERSION = 3
BASE_DIFFICULTY = [42, 50, 57]
FINANCE_MUTATION_IDS = {
    "source_triangulation",
    "filing_recency_guard",
    "accounting_normalizer",
    "earnings_quality_check",
    "valuation_sensitivity",
    "risk_register",
}
BROWSER_ONLY_MUTATION_IDS = {"semantic_locator", "screenshot_ocr", "visual_locator"}


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


def _build_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "stats": deepcopy(state.get("stats", {})),
        "stability": int(state.get("stability", 0)),
        "compute": int(state.get("compute", 0)),
        "complexityUsed": int(state.get("complexityUsed", 0)),
        "mutationIds": list(state.get("mutationIds", [])),
        "evolutionIds": list(state.get("evolutionIds", [])),
    }


def _find_map_node(
    state: dict[str, Any], node_id: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for region in state.get("map", []):
        for layer in region.get("layers", []):
            for node in layer:
                if node.get("id") == node_id:
                    return region, node
    return None


def _node_record(state: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in state.get("nodeHistory", []) if item.get("nodeId") == node_id),
        None,
    )


def _start_node_record(state: dict[str, Any], node: dict[str, Any]) -> None:
    state.setdefault("nodeHistory", [])
    if _node_record(state, str(node["id"])) is not None:
        return
    region = get_current_region(state) or {}
    state["nodeHistory"].append(
        {
            "nodeId": node["id"],
            "sequence": len(state["nodeHistory"]) + 1,
            "act": int(node.get("act") or state.get("actIndex", 0) + 1),
            "regionId": node.get("regionId") or region.get("id"),
            "regionName": str(region.get("name") or node.get("regionId") or "Unknown Region"),
            "layer": int(node.get("layer", state.get("layerIndex", 0))),
            "type": str(node.get("type") or "normal"),
            "difficulty": int(node.get("difficulty", 0)),
            "monsterId": node.get("monsterId"),
            "status": "entered",
            "before": _build_snapshot(state),
            "result": None,
            "reward": {
                "mutationDraftIds": [],
                "selectedMutationId": None,
                "skipped": False,
                "unlockedEvolutionIds": [],
            },
            "after": None,
            "logIds": [],
            "legacyIncomplete": False,
        }
    )


def _append_node_log_ids(state: dict[str, Any], node_id: str, start_index: int) -> None:
    record = _node_record(state, node_id)
    if record is None:
        return
    known = set(record.get("logIds", []))
    for item in state.get("logs", [])[start_index:]:
        log_id = item.get("id")
        if log_id is not None and log_id not in known:
            record.setdefault("logIds", []).append(log_id)
            known.add(log_id)


def normalize_run_state(state: dict[str, Any]) -> dict[str, Any]:
    """Upgrade persisted Run state without inventing unavailable historical evidence."""

    normalized = deepcopy(state)
    if normalized.get("saveVersion") == SAVE_VERSION and isinstance(
        normalized.get("nodeHistory"), list
    ):
        normalized.setdefault("nodeHistoryIncomplete", False)
        return normalized

    completed_node_ids = [str(item) for item in normalized.get("completedNodeIds", [])]
    completed_ids = set(completed_node_ids)
    encounter_by_node = {
        str(result.get("nodeId")): result
        for result in normalized.get("encounterHistory", [])
        if isinstance(result, dict) and result.get("nodeId")
    }
    ordered_node_ids = list(completed_node_ids)
    ordered_node_ids.extend(
        node_id for node_id in encounter_by_node if node_id not in completed_ids
    )
    history: list[dict[str, Any]] = []
    for node_id in ordered_node_ids:
        found = _find_map_node(normalized, node_id)
        if not found:
            continue
        region, node = found
        result = encounter_by_node.get(node_id)
        terminal_failure = bool(
            normalized.get("status") == "defeat" and normalized.get("selectedNodeId") == node_id
        )
        history.append(
            {
                "nodeId": node_id,
                "sequence": len(history) + 1,
                "act": int(node.get("act", 1)),
                "regionId": node.get("regionId") or region.get("id"),
                "regionName": str(region.get("name") or node.get("regionId") or "Unknown Region"),
                "layer": int(node.get("layer", 0)),
                "type": str(node.get("type") or "normal"),
                "difficulty": int(node.get("difficulty", 0)),
                "monsterId": node.get("monsterId"),
                "status": "failed" if terminal_failure else "completed",
                "before": None,
                "result": deepcopy(result) if result is not None else None,
                "reward": {
                    "mutationDraftIds": [],
                    "selectedMutationId": None,
                    "skipped": False,
                    "unlockedEvolutionIds": [],
                },
                "after": None,
                "logIds": [],
                "legacyIncomplete": True,
            }
        )
    normalized["saveVersion"] = SAVE_VERSION
    normalized["nodeHistory"] = history
    normalized["nodeHistoryIncomplete"] = bool(ordered_node_ids)
    return normalized


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


def generate_map(seed: str, scenario_id: str = "browser") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    source_regions = FINANCE_REGIONS if scenario_id == "finance" else REGIONS
    for act_index, source_region in enumerate(source_regions):
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
    if skill_genome and skill_genome.get("metadata", {}).get("category") == "finance":
        archetype_id = "finance"
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
        "scenarioId": archetype["id"],
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
        "map": generate_map(normalized_seed, archetype["id"]),
        "completedNodeIds": [],
        "encounterHistory": [],
        "nodeHistory": [],
        "nodeHistoryIncomplete": False,
        "currentDraft": [],
        "lastResult": None,
        "logs": [],
    }
    return _with_log(
        run,
        f"以 {skill_name} 启动「{mode['name']}」Evaluation Run，Run Seed：{normalized_seed}。",
        "accent",
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
        else "Candidate Generator"
        if node["type"] == "lab"
        else "Budget Recovery"
    )
    next_state = deepcopy(state)
    next_state.update(
        {"phase": "encounter", "selectedNodeId": node["id"], "currentDraft": [], "lastResult": None}
    )
    _start_node_record(next_state, node)
    log_start = len(next_state["logs"])
    next_state = _with_log(next_state, f"选择测试：{label}。")
    _append_node_log_ids(next_state, node["id"], log_start)
    return next_state


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
    automatic_target_gain = 0.0
    selected_monster_ids = state.get("automation", {}).get("selectedMonsterIds", [])
    for monster_id in selected_monster_ids:
        target = MONSTERS.get(monster_id)
        if not target:
            continue
        automatic_target_gain += sum(
            max(0, mutation["effects"].get(stat, 0)) * weight
            for stat, weight in target["requirements"].items()
        )
    return (
        encounter_gain * 1.5
        + mode_gain
        + automatic_target_gain * 1.2
        + rarity_boost
        + random() * 12
    )


def create_mutation_draft(state: dict[str, Any], node: dict[str, Any] | None = None) -> list[str]:
    node = node or get_selected_node(state)
    monster = MONSTERS.get(node["monsterId"]) if node and node.get("monsterId") else None
    random = create_rng(
        f"{state['seed']}|draft|{node['id'] if node else 'free'}|{','.join(state['mutationIds'])}|{state['modeId']}"
    )
    remaining = state["complexityMax"] - state["complexityUsed"]
    scenario_id = state.get("scenarioId", "browser")
    available = [
        item
        for item in MUTATIONS
        if item["id"] not in state["mutationIds"]
        and item["complexityCost"] <= remaining
        and not (scenario_id == "finance" and item["id"] in BROWSER_ONLY_MUTATION_IDS)
        and not (scenario_id != "finance" and item["id"] in FINANCE_MUTATION_IDS)
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
    next_state = _complete_selected_node(next_state)
    record = _node_record(next_state, node["id"])
    if record is not None:
        record["result"] = deepcopy(next_state["lastResult"])
        record["status"] = "completed"
        record["after"] = _build_snapshot(next_state)
    log_start = len(next_state["logs"])
    next_state = _with_log(
        _advance_layer(next_state),
        f"恢复运行预算：Failure Budget +{healed}，Compute Budget +10。",
        "success",
    )
    _append_node_log_ids(next_state, node["id"], log_start)
    return next_state


def _resolve_lab_node(state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    next_state = _complete_selected_node(state)
    draft = create_mutation_draft(state, node)
    next_state.update(
        {
            "phase": "reward",
            "currentDraft": draft,
            "lastResult": {"nodeId": node["id"], "kind": "lab"},
        }
    )
    record = _node_record(next_state, node["id"])
    if record is not None:
        record["result"] = deepcopy(next_state["lastResult"])
        record["reward"]["mutationDraftIds"] = list(draft)
    log_start = len(next_state["logs"])
    next_state = _with_log(
        next_state,
        "Candidate Generator 已生成一组 Candidate Change，不执行当前 Benchmark。",
        "accent",
    )
    _append_node_log_ids(next_state, node["id"], log_start)
    return next_state


def _resolve_boss(
    state: dict[str, Any], node: dict[str, Any], result: dict[str, Any], settled: dict[str, Any]
) -> dict[str, Any]:
    next_state = deepcopy(settled)
    if not result["passed"]:
        next_state.update({"status": "defeat", "phase": "ended", "currentDraft": []})
        return _with_log(
            next_state,
            f"{MONSTERS[node['monsterId']]['name']} 未通过 Hidden Holdout，本次 Candidate Run 终止。",
            "danger",
        )
    if state["actIndex"] == len(state["map"]) - 1:
        next_state.update({"status": "victory", "phase": "ended", "currentDraft": []})
        return _with_log(
            next_state,
            "最终 Hidden Holdout 通过：该 Skill 获得 Candidate AgentPreset 资格。",
            "success",
        )
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
        f"Hidden Holdout 通过，进入 Stage {state['actIndex'] + 2}「{next_region['name']}」。",
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
    log_start = len(state["logs"])
    result = evaluate_encounter(state, node)
    assert result is not None
    next_stability = max(0, state["stability"] - result["stabilityDamage"])
    next_compute = max(0, state["compute"] - result["computeCost"] + result["computeReward"])
    settled = deepcopy(state)
    settled.update({"stability": next_stability, "compute": next_compute, "lastResult": result})
    settled["encounterHistory"].append(result)
    settled = _complete_selected_node(settled)
    monster = MONSTERS[node["monsterId"]]
    outcome = "通过" if result["passed"] else f"失败，Failure Budget -{result['stabilityDamage']}"
    settled = _with_log(
        settled,
        f"{monster['name']}：Coverage {result['coverage']}% / {result['threshold']}%，{outcome}。",
        "success" if result["passed"] else "danger",
    )
    record = _node_record(settled, node["id"])
    if record is not None:
        record["result"] = deepcopy(result)
    if node["type"] == "boss":
        resolved = _resolve_boss(state, node, result, settled)
        record = _node_record(resolved, node["id"])
        if record is not None:
            record["status"] = "completed" if result["passed"] else "failed"
            record["after"] = _build_snapshot(resolved)
        _append_node_log_ids(resolved, node["id"], log_start)
        return resolved
    if next_stability <= 0:
        settled.update({"status": "defeat", "phase": "ended", "currentDraft": []})
        settled = _with_log(
            settled,
            "Failure Budget 已归零，本次 Evaluation Run 失败；Replay 与失败样本已保留。",
            "danger",
        )
        record = _node_record(settled, node["id"])
        if record is not None:
            record["status"] = "failed"
            record["after"] = _build_snapshot(settled)
        _append_node_log_ids(settled, node["id"], log_start)
        return settled
    draft = create_mutation_draft(settled, node)
    settled.update({"phase": "reward", "currentDraft": draft})
    record = _node_record(settled, node["id"])
    if record is not None:
        record["reward"]["mutationDraftIds"] = list(draft)
    _append_node_log_ids(settled, node["id"], log_start)
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
                next_state,
                f"Capability Bundle 已启用：{evolution['name']}。",
                "evolution",
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
    node_id = str(next_state.get("selectedNodeId") or "")
    log_start = len(next_state["logs"])
    previous_evolutions = set(next_state.get("evolutionIds", []))
    next_state["stats"] = _apply_effects(state["stats"], mutation["effects"])
    next_state["mutationIds"].append(mutation["id"])
    next_state["complexityUsed"] += mutation["complexityCost"]
    next_state = _with_log(
        next_state,
        f"应用 Candidate Change「{mutation['name']}」：{mutation['benefit']}",
        "accent",
    )
    next_state = _unlock_evolutions(next_state)
    if node_id:
        record = _node_record(next_state, node_id)
        if record is not None:
            record["reward"]["selectedMutationId"] = mutation_id
            record["reward"]["skipped"] = False
            record["reward"]["unlockedEvolutionIds"] = [
                item
                for item in next_state.get("evolutionIds", [])
                if item not in previous_evolutions
            ]
            record["status"] = "completed"
            record["after"] = _build_snapshot(next_state)
    next_state = _advance_layer(next_state)
    if node_id:
        _append_node_log_ids(next_state, node_id, log_start)
    return next_state


def skip_mutation(state: dict[str, Any]) -> dict[str, Any]:
    if state["status"] != "active" or state["phase"] != "reward":
        return deepcopy(state)
    node_id = str(state.get("selectedNodeId") or "")
    log_start = len(state["logs"])
    next_state = _with_log(state, "跳过本次 Candidate Change，保持当前配置。")
    if node_id:
        record = _node_record(next_state, node_id)
        if record is not None:
            record["reward"]["selectedMutationId"] = None
            record["reward"]["skipped"] = True
            record["status"] = "completed"
            record["after"] = _build_snapshot(next_state)
    next_state = _advance_layer(next_state)
    if node_id:
        _append_node_log_ids(next_state, node_id, log_start)
    return next_state


def _automation_progress(state: dict[str, Any]) -> int:
    total_nodes = max(1, sum(len(region["layers"]) for region in state["map"]))
    return min(100, round(len(state["completedNodeIds"]) / total_nodes * 100))


def _update_automation(
    state: dict[str, Any],
    *,
    status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    next_state = deepcopy(state)
    automation = deepcopy(next_state.get("automation") or {})
    if status is not None:
        automation["status"] = status
    if stage is not None:
        automation["stage"] = stage
    if message is not None:
        automation["message"] = message
    automation["completedNodes"] = len(next_state["completedNodeIds"])
    automation["progress"] = _automation_progress(next_state)
    next_state["automation"] = automation
    return next_state


def start_automatic_run(
    state: dict[str, Any],
    *,
    selected_monster_ids: list[str],
    project: dict[str, str],
) -> dict[str, Any]:
    if (
        state["status"] != "active"
        or state["phase"] != "choose_node"
        or state["completedNodeIds"]
        or state.get("automation", {}).get("status") == "running"
    ):
        return deepcopy(state)
    total_nodes = sum(len(region["layers"]) for region in state["map"])
    next_state = deepcopy(state)
    next_state["automation"] = {
        "status": "running",
        "stage": "planning",
        "message": "自动 Evaluation Run 已启动，正在规划第一个测试。",
        "selectedMonsterIds": list(dict.fromkeys(selected_monster_ids)),
        "project": deepcopy(project),
        "completedNodes": 0,
        "totalNodes": total_nodes,
        "progress": 0,
    }
    return _with_log(
        next_state,
        f"自动 Evaluation Run 已启动：锁定 {len(next_state['automation']['selectedMonsterIds'])} 个目标 Failure Mode。",
        "accent",
    )


def _automatic_node_score(state: dict[str, Any], node: dict[str, Any]) -> float:
    selected = set(state.get("automation", {}).get("selectedMonsterIds", []))
    if node.get("monsterId") in selected:
        return 10_000 - node["difficulty"]
    if node["type"] == "rest":
        resource_pressure = max(0, 8 - state["stability"]) * 30 + max(0, 45 - state["compute"])
        return resource_pressure - 40
    if node["type"] == "lab":
        remaining = state["complexityMax"] - state["complexityUsed"]
        return 120 + remaining * 8 if remaining > 0 else -100
    monster = MONSTERS.get(node.get("monsterId"))
    if not monster:
        return 0
    deficit = sum(
        max(0, 82 - state["stats"].get(stat, 0)) * weight
        for stat, weight in monster["requirements"].items()
    )
    return deficit - node["difficulty"] * 0.05


def _choose_automatic_node(state: dict[str, Any]) -> dict[str, Any] | None:
    layer = get_current_layer(state)
    if not layer:
        return None
    return max(layer, key=lambda node: (_automatic_node_score(state, node), node["id"]))


def _future_automatic_monsters(state: dict[str, Any]) -> list[dict[str, Any]]:
    selected = set(state.get("automation", {}).get("selectedMonsterIds", []))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for region in state["map"][state["actIndex"] :]:
        monster_ids = [region["boss"]]
        monster_ids.extend(
            node["monsterId"]
            for layer in region["layers"]
            for node in layer
            if node.get("monsterId") in selected
        )
        for monster_id in monster_ids:
            if monster_id in seen or monster_id not in MONSTERS:
                continue
            seen.add(monster_id)
            result.append(MONSTERS[monster_id])
    return result


def _automatic_mutation_score(state: dict[str, Any], mutation: dict[str, Any]) -> float:
    score = 0.0
    for monster in _future_automatic_monsters(state):
        for stat, weight in monster["requirements"].items():
            gain = mutation["effects"].get(stat, 0)
            deficit = max(0, 85 - state["stats"].get(stat, 0))
            score += gain * weight * (1 + deficit / 40)
        if monster.get("securityFloor"):
            score += max(0, mutation["effects"].get("security", 0)) * 2.5
    score += max(0, mutation["effects"].get("robustness", 0)) * 1.2
    score += max(0, mutation["effects"].get("efficiency", 0)) * 0.7
    score += max(0, mutation["effects"].get("structure", 0)) * 0.4
    score += sum(min(0, value) for value in mutation["effects"].values()) * 0.3
    return score / max(0.75, mutation["complexityCost"])


def _choose_automatic_mutation(state: dict[str, Any]) -> str | None:
    candidates = [
        mutation
        for mutation_id in state["currentDraft"]
        if (mutation := _mutation(mutation_id)) is not None
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda mutation: (_automatic_mutation_score(state, mutation), mutation["id"]),
    )["id"]


def advance_automatic_run(state: dict[str, Any]) -> dict[str, Any]:
    automation = state.get("automation") or {}
    if automation.get("status") != "running":
        return deepcopy(state)
    if state["status"] != "active" or state["phase"] == "ended":
        victory = state["status"] == "victory"
        return _update_automation(
            state,
            status="completed" if victory else "failed",
            stage="artifact" if victory else "ended",
            message=(
                "全部 Hidden Holdout 通过，正在生成 Candidate AgentPreset。"
                if victory
                else "自动 Evaluation Run 未通过 Hidden Holdout，未生成 Candidate AgentPreset。"
            ),
        )

    if state["phase"] == "choose_node":
        node = _choose_automatic_node(state)
        if not node:
            return deepcopy(state)
        next_state = select_node(state, node["id"])
        monster = MONSTERS.get(node.get("monsterId"))
        label = (
            monster["name"]
            if monster
            else "Candidate Generator"
            if node["type"] == "lab"
            else "Budget Recovery"
        )
        return _update_automation(
            next_state,
            stage="encounter",
            message=f"正在执行：{label}。",
        )

    if state["phase"] == "encounter":
        next_state = resolve_current_node(state)
        if next_state["phase"] == "ended":
            victory = next_state["status"] == "victory"
            return _update_automation(
                next_state,
                status="completed" if victory else "failed",
                stage="artifact" if victory else "ended",
                message=(
                    "全部 Hidden Holdout 通过，正在生成 Candidate AgentPreset。"
                    if victory
                    else "自动 Evaluation Run 未通过 Hidden Holdout，未生成 Candidate AgentPreset。"
                ),
            )
        if next_state["phase"] == "reward":
            return _update_automation(
                next_state,
                stage="mutation",
                message="Evaluation 已完成，正在自动选择 Candidate Change。",
            )
        return _update_automation(
            next_state,
            stage="planning",
            message="测试已完成，正在规划下一个 Evaluation。",
        )

    if state["phase"] == "reward":
        mutation_id = _choose_automatic_mutation(state)
        next_state = choose_mutation(state, mutation_id) if mutation_id else skip_mutation(state)
        mutation = _mutation(mutation_id) if mutation_id else None
        return _update_automation(
            next_state,
            stage="planning",
            message=(
                f"已应用 Candidate Change：{mutation['name']}，正在规划下一个 Evaluation。"
                if mutation
                else "本轮没有可用 Candidate Change，正在规划下一个 Evaluation。"
            ),
        )
    return deepcopy(state)


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
    scenario_monsters = {}
    for scenario_id, regions in (("browser", REGIONS), ("finance", FINANCE_REGIONS)):
        scenario_monsters[scenario_id] = [
            {
                **deepcopy(MONSTERS[monster_id]),
                "regionId": region["id"],
                "regionName": region["name"],
            }
            for region in regions
            for monster_id in region["monsters"]
        ]
    return {
        "archetypes": ARCHETYPES,
        "evolutions": EVOLUTIONS,
        "monsters": MONSTERS,
        "scenarioMonsters": scenario_monsters,
        "mutations": MUTATIONS,
        "nodeTypes": NODE_TYPES,
        "runModes": RUN_MODES,
        "statLabels": STAT_LABELS,
    }
