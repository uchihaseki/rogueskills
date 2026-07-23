"""Run the new real Finance Case endpoint against public sources and configured Qwen."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "prior-real.db"


def write(name: str, value: object) -> None:
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


try:
    settings = Settings(
        database_url=f"sqlite:///{DATABASE}",
        project_root=Path(__file__).resolve().parents[2],
        automatic_run_step_delay_seconds=0.05,
    )
    with TestClient(create_app(settings)) as api:
        preflight = api.get("/api/finance/cases/preflight").json()
        write("30-live-preflight.json", preflight)
        library = api.get("/api/library/initial").json()["skills"]
        finance = [
            item
            for item in library
            if item.get("genome", {}).get("metadata", {}).get("category") == "finance"
        ]
        if not finance:
            raise RuntimeError("No finance Initial Skill in the isolated database")
        response = api.post(
            "/api/finance/cases",
            json={
                "ticker": "AAPL",
                "skillId": finance[0]["id"],
                "asOfDate": date(2026, 7, 21).isoformat(),
                "mode": "live",
                "autoEvolve": True,
            },
        )
        payload = response.json()
        write("31-live-aapl-case.json", payload)
        if response.status_code >= 400:
            raise RuntimeError(payload)
        case = payload["case"]
        write(
            "32-live-aapl-summary.json",
            {
                "caseId": case["id"],
                "status": case["status"],
                "runtimeVerified": case["runtimeVerified"],
                "baseSkillVersionId": case["baseSkillVersionId"],
                "evolvedSkillVersionId": case.get("evolvedSkillVersionId"),
                "baselineScore": (case.get("baseline") or {}).get("evaluation", {}).get("score"),
                "finalScore": (case.get("finalEvaluation") or {}).get("score"),
                "comparison": case.get("comparison"),
                "financeEvolutionRunId": case.get("financeEvolutionRunId"),
                "agentPresetId": (case.get("agentPreset") or {}).get("id"),
                "agentPresetDigest": (case.get("agentPreset") or {}).get("digest"),
                "sourceCount": len((case.get("finalReport") or {}).get("sources", [])),
                "factCount": len((case.get("finalReport") or {}).get("facts", [])),
            },
        )
        print(json.dumps(json.loads((ROOT / "32-live-aapl-summary.json").read_text()), ensure_ascii=False))
except Exception as error:
    write("33-live-aapl-failure.json", {"type": type(error).__name__, "message": str(error)})
    raise
