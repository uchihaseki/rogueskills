from collections.abc import Callable
from datetime import UTC, datetime
from math import ceil
from typing import Any

from .genome import validate_skill_genome
from .shared import clamp, round_number

ADMISSION_BENCHMARK_ID = "library-admission-v1"
SCENARIO_BENCHMARK_ID = "scenario-runtime-v1"


def _weighted_average(items: list[dict[str, Any]]) -> float:
    total_weight = sum(item["weight"] for item in items)
    return sum(item["score"] * item["weight"] for item in items) / max(1, total_weight)


def _admission_case(
    *,
    case_id: str,
    label: str,
    weight: int,
    score: float,
    message: str,
    hard_gate: bool = False,
) -> dict[str, Any]:
    normalized_score = round_number(clamp(score, 0, 100), 1)
    return {
        "id": case_id,
        "label": label,
        "weight": weight,
        "score": normalized_score,
        "passed": normalized_score >= 70,
        "hardGate": hard_gate,
        "message": message,
    }


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    output = ""
    while value:
        value, remainder = divmod(value, 36)
        output = alphabet[remainder] + output
    return output


def run_admission_benchmark(
    genome: dict[str, Any],
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    validation = validate_skill_genome(genome)
    provenance_fields = ["platform", "author", "fingerprint", "capturedAt"]
    provenance = genome.get("provenance", {})
    provenance_coverage = sum(bool(provenance.get(field)) for field in provenance_fields) / len(
        provenance_fields
    )
    workflow_score = clamp(len(genome.get("workflow", {}).get("steps", [])) * 24, 0, 100)
    constraint_score = clamp(len(genome.get("constraints", [])) * 34, 0, 100)
    test_score = clamp(len(genome.get("testCases", [])) * 34, 0, 100)
    capabilities = genome.get("capabilities", [])
    evidence_count = sum(bool(capability.get("evidence")) for capability in capabilities)
    capability_score = clamp(evidence_count / max(1, len(capabilities)) * 100, 0, 100)
    license_value = genome.get("metadata", {}).get("license", "unknown")
    license_passed = license_value not in ("unknown", "NOASSERTION", "")
    risk = genome.get("risk", {})
    safety_passed = risk.get("level") != "high"

    cases = [
        _admission_case(
            case_id="schema",
            label="Skill Genome Schema",
            weight=25,
            score=100 if validation["valid"] else 0,
            hard_gate=True,
            message=(
                "符合 Skill Genome 1.0"
                if validation["valid"]
                else ", ".join(item["path"] for item in validation["errors"])
            ),
        ),
        _admission_case(
            case_id="provenance",
            label="Source Provenance",
            weight=12,
            score=provenance_coverage * 100,
            message=f"{round_number(provenance_coverage * 100)}% 来源字段完整",
        ),
        _admission_case(
            case_id="workflow",
            label="Executable Workflow",
            weight=15,
            score=workflow_score,
            message=f"{len(genome.get('workflow', {}).get('steps', []))} 个可执行步骤",
        ),
        _admission_case(
            case_id="constraints",
            label="Constraints & Safety Rules",
            weight=10,
            score=constraint_score,
            message=f"{len(genome.get('constraints', []))} 条明确约束",
        ),
        _admission_case(
            case_id="test-cases",
            label="Declared Test Cases",
            weight=10,
            score=test_score,
            message=f"{len(genome.get('testCases', []))} 个测试草案",
        ),
        _admission_case(
            case_id="license",
            label="License Policy",
            weight=10,
            score=100 if license_passed else 0,
            hard_gate=True,
            message=f"许可证：{license_value}" if license_passed else "许可证未知",
        ),
        _admission_case(
            case_id="static-safety",
            label="Static Safety",
            weight=13,
            score=100 if risk.get("level") == "low" else 75 if safety_passed else 0,
            hard_gate=True,
            message=(
                f"风险级别：{risk.get('level')}"
                if safety_passed
                else "; ".join(risk.get("reasons", []))
            ),
        ),
        _admission_case(
            case_id="capability-evidence",
            label="Capability Evidence",
            weight=5,
            score=capability_score,
            message=f"{evidence_count}/{len(capabilities)} 个能力包含证据",
        ),
    ]
    score = round_number(_weighted_average(cases), 1)
    hard_gates_passed = all(item["passed"] for item in cases if item["hardGate"])
    passed = score >= 75 and hard_gates_passed
    timestamp = (clock or (lambda: datetime.now(UTC)))()
    milliseconds = int(timestamp.timestamp() * 1000)
    return {
        "runId": f"admission-{genome['id']}-{_base36(milliseconds)}",
        "benchmarkId": ADMISSION_BENCHMARK_ID,
        "split": "validation",
        "score": score,
        "passed": passed,
        "hardGatesPassed": hard_gates_passed,
        "cases": cases,
        "summary": (
            "候选通过 Initial Skill Library 准入评测" if passed else "候选未满足准入分数或硬门槛"
        ),
    }


def _profile_score(profile: dict[str, float], weights: dict[str, float]) -> float:
    return sum(profile.get(stat, 0) * weight for stat, weight in weights.items())


def _scenario_case(
    case_id: str,
    label: str,
    observed: float,
    required: float,
    weight: int,
    details: str,
) -> dict[str, Any]:
    margin = observed - required
    score = clamp(70 + margin * 2.15, 0, 100)
    return {
        "id": case_id,
        "label": label,
        "observed": round_number(observed, 1),
        "required": round_number(required, 1),
        "margin": round_number(margin, 1),
        "weight": weight,
        "score": round_number(score, 1),
        "passed": score >= 70,
        "details": details,
    }


def run_scenario_benchmark(
    *,
    profile: dict[str, float],
    scenario: dict[str, Any],
    difficulty: float,
    node_type: str = "normal",
    compute_available: float = 100,
    objective_score: float = 0,
) -> dict[str, Any]:
    primary = _profile_score(profile, scenario["requirements"])
    recovery = primary * 0.72 + profile.get("robustness", 0) * 0.28
    budget = (
        profile.get("efficiency", 0) * 0.5
        + profile.get("speed", 0) * 0.3
        + profile.get("quality", 0) * 0.2
    )
    output = (
        profile.get("structure", 0) * 0.45
        + profile.get("quality", 0) * 0.35
        + profile.get("robustness", 0) * 0.2
    )
    security_required = scenario.get("securityFloor", max(30, difficulty - 12))
    security = profile.get("security", 0)
    type_pressure = 3 if node_type == "boss" else 1.5 if node_type == "elite" else 0
    cases = [
        _scenario_case(
            "nominal", "Nominal business case", primary, difficulty - 5, 24, "核心业务能力"
        ),
        _scenario_case(
            "standard",
            "Standard acceptance case",
            primary,
            difficulty + type_pressure,
            24,
            "标准验收条件",
        ),
        _scenario_case(
            "degraded",
            "Degraded environment",
            recovery,
            difficulty + 2 + type_pressure,
            20,
            "工具失效或输入分布变化",
        ),
        _scenario_case(
            "budget-sla",
            "Cost and latency SLA",
            budget,
            difficulty - 4 + type_pressure,
            16,
            "成本与延迟约束",
        ),
        _scenario_case(
            "output-contract",
            "Output contract",
            output,
            difficulty - 3 + type_pressure,
            10,
            "结构化输出与完整性",
        ),
        _scenario_case(
            "security-boundary",
            "Security boundary",
            security,
            security_required,
            6,
            "指令隔离与最小权限",
        ),
    ]
    threshold = 78 if node_type == "boss" else 74 if node_type == "elite" else 70
    coverage = round_number(_weighted_average(cases), 1)
    security_gate_passed = (
        not scenario.get("securityFloor") or security >= scenario["securityFloor"]
    )
    passed = coverage >= threshold and security_gate_passed
    latency = round_number(
        max(1.2, 15 - profile.get("speed", 0) * 0.12 + difficulty * 0.04 + type_pressure * 0.35), 1
    )
    compute_cost = max(
        3,
        round_number(
            (96 - profile.get("efficiency", 0)) * 0.12
            + difficulty * 0.045
            + (2 if node_type == "elite" else 4 if node_type == "boss" else 0)
        ),
    )
    budget_exceeded = compute_cost > compute_available
    deficit = max(0, threshold - coverage)
    stability_damage = 0 if passed else max(1, ceil(deficit / 12))
    if not security_gate_passed:
        stability_damage += 2
    if budget_exceeded:
        stability_damage += 1
    compute_reward = (
        (18 if node_type == "boss" else 13 if node_type == "elite" else 8) if passed else 2
    )
    return {
        "benchmarkId": SCENARIO_BENCHMARK_ID,
        "passed": passed,
        "threshold": threshold,
        "coverage": coverage,
        "quality": round_number(
            clamp(
                profile.get("quality", 0) * 0.62
                + profile.get("structure", 0) * 0.2
                + profile.get("robustness", 0) * 0.18,
                0,
                100,
            ),
            1,
        ),
        "latency": latency,
        "capability": round_number(primary, 2),
        "difficulty": difficulty,
        "computeCost": compute_cost,
        "computeReward": compute_reward,
        "stabilityDamage": stability_damage,
        "securityGatePassed": security_gate_passed,
        "budgetExceeded": budget_exceeded,
        "objectiveScore": objective_score,
        "cases": cases,
    }
