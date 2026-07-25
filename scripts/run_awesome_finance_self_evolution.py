"""Run a deterministic, demo-ready Awesome Finance Skills evolution case.

The runner uses the production FastAPI composition in-process.  It imports the
local Awesome Finance Skills snapshot, promotes candidates through the normal
admission benchmark, starts a finance Evolution Run, waits for the authoritative
state machine to reach victory, and writes JSON artifacts for a demo or review.
No LLM, market data provider, or remote search is required for this path.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "awesome-finance-self-evolution-20260724"


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
    parser.add_argument(
        "--database",
        default=str(PROJECT_ROOT / "data" / "rogueskills.db"),
        help="SQLite database path; defaults to the local RogueSkills database.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR),
        help="Directory for reproducible JSON artifacts.",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        database_url=f"sqlite:///{Path(args.database).expanduser().resolve()}",
        project_root=PROJECT_ROOT,
        automatic_run_step_delay_seconds=0.02,
    )
    with TestClient(create_app(settings)) as api:
        imported = require(
            api.post(
                "/api/scenarios/finance/import-awesome",
                json={"autoPromote": True},
            ),
            "import Awesome Finance Skills",
        )
        write_json(artifact_dir, "01-awesome-import.json", imported)

        initial = require(api.get("/api/library/initial"), "list Initial Skill Library")
        write_json(artifact_dir, "02-initial-library.json", initial)

        selected = next(
            (
                item
                for item in imported["skills"]
                if item["sourceName"] == "alphaear-signal-tracker" and item["status"] == "initial"
            ),
            None,
        )
        if not selected:
            raise RuntimeError(
                "alphaear-signal-tracker was not admitted to the Initial Skill Library"
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
        write_json(artifact_dir, "03-run-created.json", created)
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
                    "projectName": "Awesome Finance 公开资料研究 Agent",
                    "projectDescription": (
                        "把 AlphaEar 的投资信号追踪工作流，进化成可追溯的上市公司研究 Agent。"
                    ),
                    "scenario": "公开披露、财报、估值与风险分析",
                },
            ),
            "start automatic finance Evolution Run",
        )
        write_json(artifact_dir, "04-run-auto-started.json", started)

        current = started
        deadline = time.monotonic() + 90
        while current["run"].get("automation", {}).get("status") == "running":
            if time.monotonic() > deadline:
                raise TimeoutError(
                    "automatic finance Evolution Run did not finish within 90 seconds"
                )
            time.sleep(0.05)
            current = require(
                api.get(f"/api/runs/{run_id}"), "poll automatic finance Evolution Run"
            )
        write_json(artifact_dir, "05-run-final.json", current)
        if current["run"]["status"] != "victory":
            raise RuntimeError(
                "automatic finance Evolution Run ended without victory: "
                f"{current['run']['status']} / {current['run'].get('automation')}"
            )

        preset = current.get("artifact")
        if not preset:
            raise RuntimeError("victory finance Evolution Run did not produce an AgentPreset")
        write_json(artifact_dir, "06-agent-preset.json", preset)

        runtime = require(
            api.get(f"/api/agent-presets/{preset['id']}/runtime-config"),
            "load AgentPreset runtime config",
        )
        write_json(artifact_dir, "07-runtime-config.json", runtime)

        codex_context = require(
            api.get("/api/demo/context"),
            "load latest browser-to-Codex demo context",
        )

        summary = {
            "source": "local Awesome Finance Skills snapshot",
            "sourceRevision": imported["source"]["revision"],
            "importSummary": imported["summary"],
            "selectedSkill": {
                "sourceName": selected["sourceName"],
                "skillId": selected["skillId"],
                "skillVersionId": selected["skillVersionId"],
                "status": selected["status"],
                "admissionScore": (selected.get("evaluation") or {}).get("score"),
            },
            "run": {
                "id": run_id,
                "status": current["run"]["status"],
                "phase": current["run"]["phase"],
                "archetypeId": current["run"].get("archetypeId"),
                "scenarioId": current["run"].get("scenarioId"),
                "completedNodeCount": len(current["run"].get("completedNodeIds", [])),
                "mutationIds": current["run"].get("mutationIds", []),
                "evolutionIds": current["run"].get("evolutionIds", []),
                "finalStats": current["run"].get("stats", {}),
            },
            "artifact": {
                "id": preset["id"],
                "digest": preset["digest"],
                "status": preset["status"],
                "runtimeVerified": preset["evaluationEvidence"]["runtimeVerified"],
                "evidenceMode": preset["evaluationEvidence"]["mode"],
                "workflowSteps": len(preset["workflow"]),
                "tools": preset["tools"],
            },
            "codexContext": {
                "available": codex_context["available"],
                "skillId": codex_context["skill"]["id"],
                "runId": codex_context["run"]["run"]["id"],
                "presetId": codex_context["artifact"]["id"],
            },
            "demoOutcome": "admitted → finance map → automatic mutations → victory → AgentPreset",
        }
        write_json(artifact_dir, "08-summary.json", summary)
        write_json(artifact_dir, "09-codex-demo-context.json", codex_context)
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
            "99-failure.json",
            {"type": type(error).__name__, "message": str(error)},
        )
        raise
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
