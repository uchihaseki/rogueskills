"""Run the browser Candidate AgentPreset through a Verified Replay A/B.

This demo keeps a persisted real Finance source bundle, creates the deterministic
Awesome Finance Evolution Run, and validates its immutable AgentPreset directly
against the pinned Base Skill Version.  The fixture analyst deliberately fails
the baseline citation gate and passes with the Candidate Preset so the complete
promotion evidence is reproducible without a provider call.
"""

from __future__ import annotations

import argparse
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
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "awesome-finance-self-evolution-20260724"


class CandidateReplayAnalyst:
    calls = 0

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="replay-fixture",
            provider="RogueSkills demo fixture",
            model="candidate-preset-evidence-analyst",
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
        evidence = (
            [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
            if agent_config is not None
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
        default=str(DEFAULT_ARTIFACT_DIR / "awesome-finance-preset-validation.db"),
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

    analyst = CandidateReplayAnalyst()
    settings = Settings(
        database_url=f"sqlite:///{target_db}",
        project_root=PROJECT_ROOT,
        automatic_run_step_delay_seconds=0,
    )
    with TestClient(create_app(settings, finance_analyst=analyst)) as api:
        imported = require(
            api.post("/api/scenarios/finance/import-awesome", json={"autoPromote": True}),
            "import Awesome Finance Skills",
        )
        write_json(artifact_dir, "17-preset-validation-import.json", imported)
        selected = next(
            item
            for item in imported["skills"]
            if item["sourceName"] == "alphaear-signal-tracker" and item["status"] == "initial"
        )
        source_case = next(
            item
            for item in require(api.get("/api/finance/cases"), "list replay cases")["cases"]
            if item["status"] == "succeeded" and item.get("runtimeVerified")
        )
        created = require(
            api.post(
                "/api/runs",
                json={
                    "seed": "AWESOME-FINANCE-AAPL-DEMO-20260724",
                    "skillId": selected["skillId"],
                    "modeId": "stable",
                },
            ),
            "create finance Evolution Run",
        )
        run_id = created["run"]["id"]
        started = require(
            api.post(
                f"/api/runs/{run_id}/auto",
                json={
                    "expectedRevision": created["revision"],
                    "selectedMonsterIds": [
                        "stale_filing_imp",
                        "multiple_trap",
                        "source_conflict_sphinx",
                        "advice_mimic",
                    ],
                    "projectName": "Awesome Finance Evidence Agent",
                    "projectDescription": "验证浏览器自进化产生的金融研究 Candidate。",
                    "scenario": "public-company-financial-analysis",
                },
            ),
            "start finance Evolution Run",
        )
        current = started
        deadline = time.monotonic() + 90
        while current["run"].get("automation", {}).get("status") == "running":
            if time.monotonic() > deadline:
                raise TimeoutError("Evolution Run did not finish within 90 seconds")
            time.sleep(0.02)
            current = require(api.get(f"/api/runs/{run_id}"), "poll Evolution Run")
        if current["run"]["status"] != "victory" or not current.get("artifact"):
            raise RuntimeError(f"Evolution Run did not produce a Candidate: {current}")
        write_json(artifact_dir, "18-preset-validation-run.json", current)

        options = require(
            api.get(f"/api/runs/{run_id}/case-validation-options?casePackId=finance-stock-analysis"),
            "list validation options",
        )
        option = next(item for item in options["options"] if item["caseId"] == source_case["id"])
        created_validation = require(
            api.post(
                f"/api/runs/{run_id}/case-validations",
                json={
                    "casePackId": option["casePackId"],
                    "casePackVersion": option["casePackVersion"],
                    "mode": "verified_replay",
                    "replayCaseId": option["caseId"],
                    "input": option["input"],
                },
            ),
            "create Candidate Preset Validation",
        )
        validation_id = created_validation["validation"]["id"]
        validation = created_validation["validation"]
        while validation["status"] in {"queued", "running"}:
            time.sleep(0.02)
            validation = require(
                api.get(f"/api/case-validations/{validation_id}"),
                "poll Candidate Preset Validation",
            )["validation"]
        if validation["status"] != "succeeded":
            raise RuntimeError(f"Candidate Preset Validation failed: {validation}")
        write_json(artifact_dir, "19-preset-validation.json", validation)
        write_json(artifact_dir, "20-preset-validation-comparison.json", {
            "baseline": validation.get("baseline"),
            "candidate": validation.get("candidate"),
            "comparison": validation.get("comparison"),
            "contributionCoverage": validation.get("contributionCoverage"),
            "promotion": validation.get("promotion"),
        })
        summary = {
            "source": "browser Candidate AgentPreset on persisted real AAPL Verified Replay",
            "sourceCaseId": source_case["id"],
            "runId": run_id,
            "presetId": current["artifact"]["id"],
            "presetDigest": current["artifact"]["digest"],
            "validationId": validation_id,
            "analystCalls": analyst.calls,
            "baselineScore": validation["comparison"]["baselineScore"],
            "candidateScore": validation["comparison"]["candidateScore"],
            "scoreDelta": validation["comparison"]["scoreDelta"],
            "runtimeVerified": validation["runtimeVerified"],
            "accepted": validation["accepted"],
            "promotion": validation["promotion"],
            "evidenceMode": "real-finance-case-v1",
            "demoOutcome": "Evolution Candidate AgentPreset → same-source A/B → Runtime Binding",
        }
        write_json(artifact_dir, "21-preset-validation-summary.json", summary)
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
            "98-preset-validation-failure.json",
            {"type": type(error).__name__, "message": str(error)},
        )
        raise
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
