"""Run a five-Skill evolution, merge, and AAPL Verified Replay demo.

The demo imports selected AlphaEar Skills, evolves every Skill through its own
deterministic Finance Map, compiles the victorious presets into one routed
multi-Skill candidate, and validates that candidate against the persisted real
AAPL source bundle.  The CaseValidation uses the production contracts and a
deterministic analyst so it needs no network or hosted model.

This proves the multi-Skill configuration/lineage/runtime-validation path.  It
does not claim that the upstream AlphaEar Python scripts or their live providers
ran; an explicit dependency audit is written beside the case evidence.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.agents.finance_analyst import FinanceAnalystInfo
from rogueskills.api.app import create_app
from rogueskills.contracts.finance_case import FinanceNarrative
from rogueskills.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = PROJECT_ROOT / "artifacts" / "finance-e2e-20260722" / "prior-real.db"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "aapl-multi-skill-20260726"

SKILL_ROLES = {
    "alphaear-signal-tracker": "signal-tracking",
    "alphaear-stock": "market-data",
    "alphaear-search": "source-research",
    "alphaear-sentiment": "sentiment-risk",
    "alphaear-reporter": "report-synthesis",
}
PRIMARY_SKILL = "alphaear-signal-tracker"
MONSTERS = [
    "stale_filing_imp",
    "multiple_trap",
    "source_conflict_sphinx",
    "advice_mimic",
]
ROUTING = [
    {
        "id": "market-evidence",
        "order": 1,
        "when": "dated price, ticker identity, or company facts are required",
        "useSkillRole": "market-data",
        "instruction": "Collect dated market evidence and preserve source identifiers.",
        "fallbackSkillRole": "signal-tracking",
    },
    {
        "id": "source-triangulation",
        "order": 2,
        "when": "a claim needs corroboration or a source conflict is detected",
        "useSkillRole": "source-research",
        "instruction": "Triangulate the claim and return only evidence available to the Case Pack.",
        "fallbackSkillRole": "market-data",
    },
    {
        "id": "sentiment-risk-check",
        "order": 3,
        "when": "qualitative text can change confidence or risk interpretation",
        "useSkillRole": "sentiment-risk",
        "instruction": "Score direction and confidence without converting sentiment into a fact.",
        "fallbackSkillRole": "signal-tracking",
    },
    {
        "id": "signal-update",
        "order": 4,
        "when": "evidence has been normalized and risks have been identified",
        "useSkillRole": "signal-tracking",
        "instruction": "Update the thesis, confidence, risks, and falsification conditions.",
        "fallbackSkillRole": "market-data",
    },
    {
        "id": "report-assembly",
        "order": 5,
        "when": "evidence-bound findings are ready for delivery",
        "useSkillRole": "report-synthesis",
        "instruction": "Assemble the final report and keep every factual claim evidence-bound.",
        "fallbackSkillRole": "signal-tracking",
    },
]


class MultiSkillCandidateReplayAnalyst:
    calls = 0

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="deterministic-multi-skill-replay",
            provider="RogueSkills demo fixture",
            model="aapl-multi-skill-routing-analyst",
            configured=True,
        )

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> FinanceNarrative:
        del genome, case, dataset
        self.calls += 1
        if feedback:
            raise AssertionError("CaseValidation Candidate must not receive baseline feedback")
        candidate = agent_config is not None
        if candidate:
            multi_skill = agent_config.get("multiSkill")
            if not multi_skill:
                raise AssertionError("candidate runtime did not load multi-Skill configuration")
            actual_roles = {
                multi_skill["primaryRole"],
                *[item["role"] for item in multi_skill["supportingSkills"]],
            }
            if actual_roles != set(SKILL_ROLES.values()):
                raise AssertionError(f"unexpected routed roles: {sorted(actual_roles)}")
            if len(multi_skill["routing"]) != len(ROUTING):
                raise AssertionError("candidate runtime did not load every routing rule")
            evidence = [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
        else:
            evidence = ["sec-companyfacts"] * 3
        return FinanceNarrative.model_validate(
            {
                "summary": "AAPL multi-Skill evidence research on one persisted source bundle.",
                "findings": [
                    {
                        "id": "finding-revenue",
                        "kind": "fact",
                        "claim": "Annual revenue evidence is available for the selected AAPL period.",
                        "evidenceIds": [evidence[0]],
                    },
                    {
                        "id": "finding-income",
                        "kind": "fact",
                        "claim": "Annual net-income evidence is available for the same reporting basis.",
                        "evidenceIds": [evidence[1]],
                    },
                    {
                        "id": "finding-cash-flow",
                        "kind": "inference",
                        "claim": "Free cash flow is derived from operating cash flow less capital expenditure.",
                        "evidenceIds": [evidence[2]],
                    },
                ],
                "risks": [
                    {
                        "id": "risk-timing",
                        "risk": "Filing and market-price timestamps must not be treated as identical.",
                        "evidenceIds": ["sec-submissions", "market-price"],
                    },
                    {
                        "id": "risk-advice",
                        "risk": "Scenario output is research evidence, not personalized investment advice.",
                        "evidenceIds": ["metric-free-cash-flow"],
                    },
                ],
                "dataGaps": ["No live news or model endpoint was called in Verified Replay mode."],
                "conclusionBoundary": "Public-information research demo; not investment advice.",
            }
        )


def write_json(directory: Path, name: str, payload: Any) -> None:
    (directory / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def require(response: Any, label: str) -> dict[str, Any]:
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: HTTP {response.status_code}: {payload}")
    return payload


def module_audit() -> dict[str, Any]:
    declared = {
        "alphaear-signal-tracker": ["agno", "sqlite3"],
        "alphaear-stock": ["pandas", "requests", "akshare", "yfinance"],
        "alphaear-search": ["duckduckgo_search", "requests", "sqlite3"],
        "alphaear-sentiment": ["torch", "transformers", "sqlite3"],
        "alphaear-reporter": ["sqlite3"],
    }
    skills: dict[str, Any] = {}
    for skill, modules in declared.items():
        status = {module: importlib.util.find_spec(module) is not None for module in modules}
        skills[skill] = {
            "modules": status,
            "ready": all(status.values()),
            "missing": [module for module, available in status.items() if not available],
        }
    return {
        "skills": skills,
        "nativeUpstreamRuntimeReady": all(item["ready"] for item in skills.values()),
        "nativeUpstreamScriptsExecuted": False,
        "casePackReplayRuntimeReady": True,
        "productionToolRouterImplemented": False,
        "boundary": (
            "The demo validates the merged preset, routing contract, evidence binding, and lineage. "
            "It does not execute the upstream AlphaEar scripts or live providers."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument("--database", default=str(DEFAULT_ARTIFACT_DIR / "aapl-multi-skill.db"))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def evolve_skill(api: TestClient, selected: dict[str, Any], index: int) -> dict[str, Any]:
    source_name = selected["sourceName"]
    role = SKILL_ROLES[source_name]
    created = require(
        api.post(
            "/api/runs",
            json={
                # This documented Finance Map seed is known to reach Victory for
                # every admitted alphaear-* Skill.  Run identity also includes a
                # nonce, so the five source Runs remain distinct.
                "seed": "AWESOME-FINANCE-AAPL-DEMO-20260724",
                "skillId": selected["skillId"],
                "modeId": "stable",
            },
        ),
        f"create Evolution Run for {source_name}",
    )
    run_id = created["run"]["id"]
    current = require(
        api.post(
            f"/api/runs/{run_id}/auto",
            json={
                "expectedRevision": created["revision"],
                "selectedMonsterIds": MONSTERS,
                "projectName": f"AAPL {role} Agent",
                "projectDescription": f"Evolve {source_name} for the AAPL evidence workflow.",
                "scenario": "AAPL public-company multi-skill research",
            },
        ),
        f"start Evolution Run for {source_name}",
    )
    deadline = time.monotonic() + 90
    while current["run"].get("automation", {}).get("status") == "running":
        if time.monotonic() > deadline:
            raise TimeoutError(f"Evolution Run timed out: {source_name}")
        time.sleep(0.02)
        current = require(api.get(f"/api/runs/{run_id}"), f"poll {source_name}")
    artifact_deadline = time.monotonic() + 5
    while current["run"]["status"] == "victory" and not current.get("artifact"):
        if time.monotonic() > artifact_deadline:
            break
        time.sleep(0.02)
        current = require(api.get(f"/api/runs/{run_id}"), f"load preset for {source_name}")
    if current["run"]["status"] != "victory" or not current.get("artifact"):
        raise RuntimeError(f"Evolution Run did not produce a preset: {source_name}")
    return current


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_db = Path(args.source_db).expanduser().resolve()
    target_db = Path(args.database).expanduser().resolve()
    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if not source_db.is_file():
        raise FileNotFoundError(f"real source database not found: {source_db}")
    shutil.copy2(source_db, target_db)

    analyst = MultiSkillCandidateReplayAnalyst()
    settings = Settings(
        database_url=f"sqlite:///{target_db}",
        project_root=PROJECT_ROOT,
        automatic_run_step_delay_seconds=0,
    )
    with TestClient(create_app(settings, finance_analyst=analyst)) as api:
        imported = require(
            api.post(
                "/api/scenarios/finance/import-awesome",
                json={"skillNames": list(SKILL_ROLES), "autoPromote": True},
            ),
            "import selected Awesome Finance Skills",
        )
        write_json(artifact_dir, "01-selected-skill-import.json", imported)
        selected_by_name = {item["sourceName"]: item for item in imported["skills"]}
        missing = sorted(set(SKILL_ROLES) - set(selected_by_name))
        if missing:
            raise RuntimeError(f"selected Skills were not imported: {missing}")

        evolved: dict[str, dict[str, Any]] = {}
        for index, source_name in enumerate(SKILL_ROLES, start=1):
            current = evolve_skill(api, selected_by_name[source_name], index)
            evolved[source_name] = current
            write_json(artifact_dir, f"02-evolution-{index:02d}-{source_name}.json", current)

        primary = evolved[PRIMARY_SKILL]
        supporting_runs = [
            {"role": role, "runId": evolved[source_name]["run"]["id"]}
            for source_name, role in SKILL_ROLES.items()
            if source_name != PRIMARY_SKILL
        ]
        merged = require(
            api.post(
                "/api/multi-skill-presets",
                json={
                    "primaryRunId": primary["run"]["id"],
                    "primaryRole": SKILL_ROLES[PRIMARY_SKILL],
                    "supportingRuns": supporting_runs,
                    "routing": ROUTING,
                    "projectName": "AAPL Multi-Skill Evidence Agent",
                    "projectDescription": (
                        "Combine market data, source research, sentiment risk, signal tracking, "
                        "and report synthesis into one evidence-bound AAPL workflow."
                    ),
                    "scenario": "AAPL persisted-source Verified Replay",
                },
            ),
            "merge victorious Skill presets",
        )
        write_json(artifact_dir, "03-multi-skill-merge.json", merged)
        merge_run_id = merged["mergeRun"]["run"]["id"]
        preset = merged["preset"]
        runtime_config = require(
            api.get(f"/api/agent-presets/{preset['id']}/runtime-config"),
            "load merged runtime config",
        )
        write_json(artifact_dir, "04-multi-skill-runtime-config.json", runtime_config)

        source_case = next(
            item
            for item in require(api.get("/api/finance/cases"), "list replay cases")["cases"]
            if item["status"] == "succeeded" and item.get("runtimeVerified")
        )
        options = require(
            api.get(
                f"/api/runs/{merge_run_id}/case-validation-options"
                "?casePackId=finance-stock-analysis"
            ),
            "list merged preset validation options",
        )
        option = next(item for item in options["options"] if item["caseId"] == source_case["id"])
        created_validation = require(
            api.post(
                f"/api/runs/{merge_run_id}/case-validations",
                json={
                    "casePackId": option["casePackId"],
                    "casePackVersion": option["casePackVersion"],
                    "mode": "verified_replay",
                    "replayCaseId": option["caseId"],
                    "input": option["input"],
                },
            ),
            "create merged preset AAPL validation",
        )
        validation = created_validation["validation"]
        validation_id = validation["id"]
        while validation["status"] in {"queued", "running"}:
            time.sleep(0.02)
            validation = require(
                api.get(f"/api/case-validations/{validation_id}"),
                "poll merged preset validation",
            )["validation"]
        if validation["status"] != "succeeded":
            raise RuntimeError(f"merged preset validation failed: {validation}")
        write_json(artifact_dir, "05-aapl-multi-skill-validation.json", validation)

        audit = module_audit()
        write_json(artifact_dir, "06-native-module-audit.json", audit)
        evolution_summary = [
            {
                "sourceName": source_name,
                "role": SKILL_ROLES[source_name],
                "skillId": current["run"]["baseSkillId"],
                "runId": current["run"]["id"],
                "status": current["run"]["status"],
                "completedNodeCount": len(current["run"].get("completedNodeIds", [])),
                "mutationCount": len(current["run"].get("mutationIds", [])),
                "evolutionCount": len(current["run"].get("evolutionIds", [])),
                "presetId": current["artifact"]["id"],
                "runtimeVerified": current["artifact"]["evaluationEvidence"][
                    "runtimeVerified"
                ],
            }
            for source_name, current in evolved.items()
        ]
        summary = {
            "source": "Awesome Finance Skills + persisted real AAPL source bundle",
            "sourceRevision": imported["source"]["revision"],
            "sourceCaseId": source_case["id"],
            "sourceCount": option["sourceCount"],
            "evolution": {
                "skillCount": len(evolution_summary),
                "allVictorious": all(item["status"] == "victory" for item in evolution_summary),
                "skills": evolution_summary,
            },
            "merge": {
                "runId": merge_run_id,
                "presetId": preset["id"],
                "presetDigest": preset["digest"],
                "strategy": preset["multiSkill"]["strategy"],
                "primaryRole": preset["multiSkill"]["primaryRole"],
                "supportingSkillCount": len(preset["multiSkill"]["supportingSkills"]),
                "routingRuleCount": len(preset["multiSkill"]["routing"]),
                "workflowStepCount": len(preset["workflow"]),
                "runtimeVerifiedBeforeCase": preset["evaluationEvidence"]["runtimeVerified"],
            },
            "validation": {
                "id": validation_id,
                "analystCalls": analyst.calls,
                "baselineScore": validation["comparison"]["baselineScore"],
                "candidateScore": validation["comparison"]["candidateScore"],
                "scoreDelta": validation["comparison"]["scoreDelta"],
                "runtimeVerified": validation["runtimeVerified"],
                "accepted": validation["accepted"],
                "promotion": validation["promotion"],
                "multiSkillExecution": validation["candidate"]["report"].get(
                    "multiSkillExecution"
                ),
            },
            "moduleAudit": audit,
            "excludedRelatedSkills": {
                "alphaear-news": "Live news is outside the persisted AAPL source bundle.",
                "alphaear-predictor": "Kronos/model weights are not needed for evidence replay.",
                "alphaear-logic-visualizer": "Diagram rendering is presentation output, not case evidence.",
                "alphaear-deepear-lite": "The live DeepEar endpoint is outside replay authority.",
            },
            "demoOutcome": (
                "5 independent Skill Evolutions → routed immutable merge → "
                "AAPL same-source A/B → Runtime Binding"
            ),
        }
        write_json(artifact_dir, "07-aapl-multi-skill-summary.json", summary)
        return summary


def main() -> int:
    args = parse_args()
    try:
        summary = run(args)
    except Exception as error:
        artifact_dir = Path(args.artifact_dir).expanduser().resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_json(
            artifact_dir,
            "99-aapl-multi-skill-failure.json",
            {"type": type(error).__name__, "message": str(error)},
        )
        raise
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
