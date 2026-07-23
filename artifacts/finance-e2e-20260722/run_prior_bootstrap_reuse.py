"""Check idempotent reuse of the two previously admitted finance SOP Skills."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "prior-real.db"


with TestClient(
    create_app(
        Settings(
            database_url=f"sqlite:///{DATABASE}",
            project_root=Path(__file__).resolve().parents[2],
            automatic_run_step_delay_seconds=0.05,
        )
    )
) as api:
    before = api.get("/api/library/initial").json()
    result_response = api.post(
        "/api/scenarios/finance/bootstrap",
        json={"maxCommunitySkills": 2, "autoPromote": True},
    )
    result = result_response.json()
    after = api.get("/api/library/initial").json()
    payload = {
        "httpStatus": result_response.status_code,
        "beforeFinanceInitialCount": sum(
            item.get("genome", {}).get("metadata", {}).get("category") == "finance"
            for item in before.get("skills", [])
        ),
        "afterFinanceInitialCount": sum(
            item.get("genome", {}).get("metadata", {}).get("category") == "finance"
            for item in after.get("skills", [])
        ),
        "summary": result.get("summary"),
        "sops": result.get("sops"),
        "providerStatus": result.get("providerStatus"),
    }
    (ROOT / "29-prior-bootstrap-reuse.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))
