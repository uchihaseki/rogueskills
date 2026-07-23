"""Verify the production evolution/preset path using a previously real finance Skill."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "prior-real.db"


def write_json(name: str, payload: Any) -> None:
    (ROOT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def require(response: Any, label: str) -> dict[str, Any]:
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: HTTP {response.status_code}: {payload}")
    return payload


def main() -> None:
    settings = Settings(
        database_url=f"sqlite:///{DATABASE}",
        project_root=Path(__file__).resolve().parents[2],
        automatic_run_step_delay_seconds=0.05,
    )
    with TestClient(create_app(settings)) as api:
        initial = require(api.get("/api/library/initial"), "initial library")
        write_json("21-prior-initial-library.json", initial)
        finance_skills = [
            item
            for item in initial["skills"]
            if item.get("genome", {}).get("metadata", {}).get("category") == "finance"
        ]
        if not finance_skills:
            raise RuntimeError("the copied database has no existing finance Initial Skill")
        selected_skill = finance_skills[0]

        created = require(
            api.post(
                "/api/runs",
                json={
                    "seed": "FINANCE-PRIOR-E2E-20260722",
                    "skillId": selected_skill["id"],
                    "modeId": "stable",
                },
            ),
            "create finance evolution run",
        )
        write_json("22-prior-run-created.json", created)
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
                    ],
                    "projectName": "公开资料股票研究 Agent",
                    "projectDescription": "基于公开披露、财报与估值假设生成可追溯的股票研究结果。",
                    "scenario": "上市公司基本面、财报、估值与风险分析",
                },
            ),
            "start automatic evolution",
        )
        write_json("23-prior-run-auto-started.json", started)

        current = started
        deadline = time.monotonic() + 90
        while current["run"].get("automation", {}).get("status") == "running":
            if time.monotonic() > deadline:
                raise TimeoutError("automatic evolution did not finish within 90 seconds")
            time.sleep(0.1)
            current = require(api.get(f"/api/runs/{run_id}"), "poll automatic evolution")
        write_json("24-prior-run-final.json", current)
        if current["run"]["status"] != "victory":
            raise RuntimeError(
                f"automatic evolution ended without victory: {current['run']['status']}"
            )
        artifact = current.get("artifact")
        if not artifact:
            raise RuntimeError("victory run did not produce an AgentPreset artifact")
        write_json("25-prior-agent-preset.json", artifact)

        preset_id = artifact["id"]
        runtime = require(
            api.get(f"/api/agent-presets/{preset_id}/runtime-config"),
            "load runtime config",
        )
        write_json("26-prior-runtime-config.json", runtime)
        package = api.get(f"/api/agent-presets/{preset_id}/export/universal")
        if package.status_code >= 400:
            raise RuntimeError(f"export failed: HTTP {package.status_code}: {package.text}")
        (ROOT / "27-prior-agent-preset-universal.zip").write_bytes(package.content)
        summary = {
            "source": "copied existing data/rogueskills.db; no new search or normalization",
            "selectedSkillId": selected_skill["id"],
            "selectedSkillName": selected_skill["name"],
            "runId": run_id,
            "runStatus": current["run"]["status"],
            "automation": current["run"].get("automation"),
            "archetypeId": current["run"].get("archetypeId"),
            "completedNodeCount": len(current["run"].get("completedNodeIds", [])),
            "mutationIds": current["run"].get("mutationIds", []),
            "evolutionIds": current["run"].get("evolutionIds", []),
            "artifactId": artifact["id"],
            "artifactDigest": artifact["digest"],
            "runtimeVerified": artifact.get("evaluationEvidence", {}).get("runtimeVerified"),
            "exportBytes": len(package.content),
        }
        write_json("28-prior-evolution-summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write_json("98-prior-evolution-failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
