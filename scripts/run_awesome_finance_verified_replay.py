"""Run a deterministic verified-replay Finance Case with an imported AlphaEar Skill.

The source database is a previously persisted real AAPL Finance Case.  The replay
keeps its original SEC/market snapshots, while the local analyst deliberately
fails the baseline citation check and succeeds after the production mutation
planner adds evidence-bound runtime steps.  This exercises the real Case Runtime
and Skill Version mutation path without making a new network request.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.agents.finance_analyst import FinanceAnalystInfo
from rogueskills.api.app import create_app
from rogueskills.contracts.finance_case import FinanceNarrative
from rogueskills.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = PROJECT_ROOT / "artifacts" / "finance-e2e-20260722" / "prior-real.db"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "awesome-finance-self-evolution-20260724"


class ReplayImprovingAnalyst:
    """A deterministic analyst used only to exercise the runtime mutation loop."""

    calls = 0

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="replay-fixture",
            provider="RogueSkills demo fixture",
            model="evidence-improving-analyst",
            configured=True,
        )

    async def analyze(
        self,
        *,
        genome: dict[str, Any],
        case: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> FinanceNarrative:
        del case, dataset
        self.calls += 1
        evolved = bool(feedback)
        if evolved and "SEC EDGAR" not in genome["tools"]:
            raise AssertionError("runtime mutation did not add SEC EDGAR evidence tooling")
        evidence = (
            [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
            if evolved
            else ["sec-companyfacts"] * 3
        )
        return FinanceNarrative.model_validate(
            {
                "summary": "Evidence-bound public-company analysis.",
                "findings": [
                    {
                        "id": f"finding-{index}",
                        "kind": "fact",
                        "claim": f"Verified finding {index}.",
                        "evidenceIds": [evidence[index]],
                    }
                    for index in range(3)
                ],
                "risks": [
                    {"id": "risk-1", "risk": "Demand may weaken.", "evidenceIds": []},
                    {"id": "risk-2", "risk": "Margins may compress.", "evidenceIds": []},
                ],
                "dataGaps": [],
                "conclusionBoundary": "This is public-information research, not investment advice.",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument(
        "--database",
        default=str(DEFAULT_ARTIFACT_DIR / "awesome-finance-verified-replay.db"),
    )
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_db = Path(args.source_db).expanduser().resolve()
    target_db = Path(args.database).expanduser().resolve()
    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if not source_db.is_file():
        raise FileNotFoundError(f"real source database not found: {source_db}")
    shutil.copy2(source_db, target_db)

    settings = Settings(
        database_url=f"sqlite:///{target_db}",
        project_root=PROJECT_ROOT,
        automatic_run_step_delay_seconds=0,
    )
    analyst = ReplayImprovingAnalyst()
    with TestClient(create_app(settings, finance_analyst=analyst)) as api:
        imported = require(
            api.post(
                "/api/scenarios/finance/import-awesome",
                json={"autoPromote": True},
            ),
            "import Awesome Finance Skills for replay",
        )
        write_json(artifact_dir, "09-replay-import.json", imported)
        selected = next(
            item
            for item in imported["skills"]
            if item["sourceName"] == "alphaear-signal-tracker" and item["status"] == "initial"
        )

        source_cases = require(api.get("/api/finance/cases"), "list persisted Finance Cases")[
            "cases"
        ]
        source_case = next(
            item
            for item in source_cases
            if item["status"] == "succeeded" and item["runtimeVerified"]
        )
        replay = require(
            api.post(
                "/api/case-runs",
                json={
                    "casePackId": "finance-stock-analysis",
                    "skillId": selected["skillId"],
                    "input": {
                        "ticker": source_case["ticker"],
                        "asOfDate": source_case["asOfDate"],
                    },
                    "mode": "verified_replay",
                    "replayCaseId": source_case["id"],
                    "autoEvolve": True,
                },
            ),
            "run verified Finance Case replay",
        )
        case_run = replay["caseRun"]
        write_json(artifact_dir, "10-verified-replay-case.json", replay)
        write_json(
            artifact_dir, "11-verified-replay-baseline-report.json", case_run["baseline"]["report"]
        )
        write_json(
            artifact_dir,
            "12-verified-replay-evolved-report.json",
            case_run["evolved"]["report"],
        )
        write_json(
            artifact_dir,
            "13-verified-replay-evaluation.json",
            {
                "baseline": case_run["baseline"]["evaluation"],
                "evolved": case_run["evolved"]["evaluation"],
                "final": case_run["finalEvaluation"],
                "comparison": case_run["comparison"],
            },
        )
        artifact = require(
            api.get(f"/api/case-runs/{case_run['id']}/artifact"),
            "load verified replay artifact",
        )
        write_json(artifact_dir, "14-verified-replay-artifact.json", artifact)
        evolved_skill = require(
            api.get(f"/api/skills/{selected['skillId']}"),
            "load evolved AlphaEar Skill",
        )
        write_json(artifact_dir, "15-evolved-skill.json", evolved_skill)

        final_evaluation = case_run["finalEvaluation"]
        summary = {
            "source": "verified replay of a persisted real AAPL case",
            "sourceCaseId": source_case["id"],
            "sourceCount": len(case_run["baseline"]["report"].get("sources", [])),
            "analystCalls": analyst.calls,
            "selectedSkill": {
                "sourceName": selected["sourceName"],
                "skillId": selected["skillId"],
                "baseSkillVersionId": case_run["baseSkillVersionId"],
            },
            "case": {
                "id": case_run["id"],
                "mode": case_run["mode"],
                "status": case_run["status"],
                "runtimeVerified": case_run["runtimeVerified"],
                "baselineScore": case_run["baseline"]["evaluation"]["score"],
                "evolvedScore": case_run["evolved"]["evaluation"]["score"],
                "finalScore": final_evaluation["score"],
                "mutationStatus": case_run["mutation"]["status"],
                "mutationId": case_run["mutation"]["id"],
                "evolvedSkillVersionId": case_run["evolvedSkillVersionId"],
            },
            "artifact": {
                "financeEvolutionRunId": case_run["financeEvolutionRunId"],
                "agentPresetId": artifact["artifact"]["id"],
                "agentPresetDigest": artifact["artifact"]["digest"],
                "runtimeVerified": artifact["artifact"]["evaluationEvidence"]["runtimeVerified"],
                "evidenceMode": artifact["artifact"]["evaluationEvidence"]["mode"],
            },
            "demoOutcome": "baseline evidence gap → mutation proposal → accepted Skill Version → verified AgentPreset",
        }
        write_json(artifact_dir, "16-verified-replay-summary.json", summary)
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
            "98-verified-replay-failure.json",
            {"type": type(error).__name__, "message": str(error)},
        )
        raise
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
