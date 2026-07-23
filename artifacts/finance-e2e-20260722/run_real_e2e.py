"""Run the finance bootstrap and evolution flow with the real configured adapters.

This is deliberately an in-process HTTP test of the production FastAPI app. It does
not replace the GitHub, raw-content, or LLM clients and it does not inject fixtures.
The only difference from the browser path is that it avoids opening a local socket
when the execution environment cannot grant a listener.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "rogueskills.db"


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
        health = require(api.get("/api/health"), "health")
        providers = require(api.get("/api/discovery/providers"), "provider discovery")
        write_json("01-health.json", health)
        write_json("02-providers.json", providers)

        search = require(
            api.post(
                "/api/discovery/search",
                json={
                    "query": "stock fundamental analysis agent skill valuation financial statements",
                    "sourceIds": ["github"],
                },
            ),
            "real GitHub search",
        )
        write_json("03-real-github-search.json", search)

        bootstrap = require(
            api.post(
                "/api/scenarios/finance/bootstrap",
                json={"maxCommunitySkills": 2, "autoPromote": True},
            ),
            "finance bootstrap",
        )
        write_json("04-finance-bootstrap.json", bootstrap)

        initial = require(api.get("/api/library/initial"), "initial library")
        write_json("05-initial-library.json", initial)
        finance_skills = [
            item
            for item in initial["skills"]
            if item.get("genome", {}).get("metadata", {}).get("category") == "finance"
        ]
        if not finance_skills:
            raise RuntimeError("bootstrap completed without a finance Initial Skill")
        selected_skill = finance_skills[0]

        catalog = require(api.get("/api/evolution/catalog"), "evolution catalog")
        write_json("06-evolution-catalog.json", catalog)
        created = require(
            api.post(
                "/api/runs",
                json={
                    "seed": "FINANCE-E2E-20260722",
                    "skillId": selected_skill["id"],
                    "modeId": "stable",
                },
            ),
            "create finance evolution run",
        )
        write_json("07-run-created.json", created)
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
                    "projectDescription": (
                        "基于公开披露、财报与估值假设生成可追溯的股票研究结果。"
                    ),
                    "scenario": "上市公司基本面、财报、估值与风险分析",
                },
            ),
            "start automatic evolution",
        )
        write_json("08-run-auto-started.json", started)

        current = started
        deadline = time.monotonic() + 90
        while current["run"].get("automation", {}).get("status") == "running":
            if time.monotonic() > deadline:
                raise TimeoutError("automatic evolution did not finish within 90 seconds")
            time.sleep(0.1)
            current = require(api.get(f"/api/runs/{run_id}"), "poll automatic evolution")
        write_json("09-run-final.json", current)

        if current["run"]["status"] != "victory":
            raise RuntimeError(
                "automatic evolution ended without victory: "
                f"{current['run']['status']} / {current['run'].get('automation')}"
            )
        artifact = current.get("artifact")
        if not artifact:
            raise RuntimeError("victory run did not produce an AgentPreset artifact")
        write_json("10-agent-preset.json", artifact)

        preset_id = artifact["id"]
        runtime = require(
            api.get(f"/api/agent-presets/{preset_id}/runtime-config"),
            "load AgentPreset runtime config",
        )
        write_json("11-runtime-config.json", runtime)
        package = api.get(f"/api/agent-presets/{preset_id}/export/universal")
        if package.status_code >= 400:
            raise RuntimeError(f"export failed: HTTP {package.status_code}: {package.text}")
        (ROOT / "12-agent-preset-universal.zip").write_bytes(package.content)

        write_json(
            "13-summary.json",
            {
                "searchResults": len(search.get("results", [])),
                "searchProviderStatus": search.get("status", []),
                "bootstrapSummary": bootstrap["summary"],
                "initialFinanceSkillIds": [item["id"] for item in finance_skills],
                "selectedSkillId": selected_skill["id"],
                "runId": run_id,
                "runStatus": current["run"]["status"],
                "automation": current["run"].get("automation"),
                "artifactId": artifact["id"],
                "artifactDigest": artifact["digest"],
                "runtimeVerified": artifact.get("evaluationEvidence", {}).get("runtimeVerified"),
                "exportBytes": len(package.content),
            },
        )
        print(json.dumps(json.loads((ROOT / "13-summary.json").read_text()), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write_json("99-failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
