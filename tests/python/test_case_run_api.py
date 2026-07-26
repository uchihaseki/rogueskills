from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings

from .fakes import FinanceFixtureMaterialNormalizer
from .test_finance_case import FixtureFinanceDataGateway, PassingFinanceAnalyst, _finance_skill


def test_generic_case_api_runs_finance_pack_and_keeps_compatibility(tmp_path: Path) -> None:
    gateway = FixtureFinanceDataGateway()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'generic-case-api.db'}",
            project_root=Path(__file__).parents[2],
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=PassingFinanceAnalyst(),
        finance_data_gateway=gateway,  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)

        packs = api.get("/api/case-packs")
        assert packs.status_code == 200
        descriptors = packs.json()["casePacks"]
        assert [item["ref"] for item in descriptors] == [
            "finance-stock-analysis@1.0.0",
            "release-readiness@1.0.0",
        ]
        assert descriptors[0] == {
            "id": "finance-stock-analysis",
            "version": "1.0.0",
            "ref": "finance-stock-analysis@1.0.0",
            "name": "Public Company Financial Analysis",
            "description": (
                "Evidence-bound public-company analysis using filings and dated market data."
            ),
            "capabilities": [
                "live",
                "verified_replay",
                "auto_evolve",
                "runtime_artifact",
                "agent_preset_validation",
            ],
        }
        detail = api.get("/api/case-packs/finance-stock-analysis")
        assert detail.status_code == 200
        assert detail.json()["casePack"]["inputSchema"]["additionalProperties"] is False
        assert detail.json()["casePack"]["skillPolicy"]["requiredCategory"] == "finance"
        preflight = api.get(
            "/api/case-runs/preflight?casePackId=finance-stock-analysis"
        )
        assert preflight.status_code == 200
        assert preflight.json()["ready"] is True
        assert preflight.json()["casePackVersion"] == "1.0.0"

        created = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": skill["id"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "live",
                "autoEvolve": False,
            },
        )
        assert created.status_code == 201
        run = created.json()["caseRun"]
        assert run["id"].startswith("case-run-")
        assert run["casePackId"] == "finance-stock-analysis"
        assert run["casePackVersion"] == "1.0.0"
        assert run["ticker"] == "AAPL"
        assert run["runtimeVerified"] is True
        assert run["agentPreset"]["evaluationEvidence"]["runtimeVerified"] is True

        loaded = api.get(f"/api/case-runs/{run['id']}")
        report = api.get(f"/api/case-runs/{run['id']}/report?stage=final")
        evaluation = api.get(f"/api/case-runs/{run['id']}/evaluation?stage=final")
        artifact = api.get(f"/api/case-runs/{run['id']}/artifact")
        listed = api.get("/api/case-runs?casePackId=finance-stock-analysis")
        finance_compat = api.get(f"/api/finance/cases/{run['id']}")

        assert loaded.status_code == 200
        assert loaded.json()["caseRun"]["id"] == run["id"]
        assert report.status_code == 200
        assert report.json()["report"]["id"] == run["finalReport"]["id"]
        assert evaluation.status_code == 200
        assert evaluation.json()["evaluation"]["hardGatesPassed"] is True
        assert artifact.status_code == 200
        assert artifact.json()["artifact"]["id"] == run["agentPreset"]["id"]
        assert [item["id"] for item in listed.json()["caseRuns"]] == [run["id"]]
        assert finance_compat.status_code == 200
        assert finance_compat.json()["case"]["id"] == run["id"]

        replayed = api.post(
            f"/api/case-runs/{run['id']}/replay",
            json={"skillId": skill["id"], "autoEvolve": False},
        )
        assert replayed.status_code == 201
        replay = replayed.json()["caseRun"]
        assert replay["mode"] == "verified_replay"
        assert replay["replayCaseId"] == run["id"]
        assert replay["runtimeVerified"] is True
        assert gateway.calls == 1


def test_generic_case_api_rejects_unknown_pack_and_invalid_input(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'generic-case-errors.db'}",
            project_root=Path(__file__).parents[2],
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=PassingFinanceAnalyst(),
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)
        missing = api.get("/api/case-packs/missing")
        invalid = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "skillId": skill["id"],
                "input": {
                    "ticker": "AAPL",
                    "asOfDate": "2026-07-22",
                    "url": "https://unapproved.example.com",
                },
                "mode": "live",
            },
        )

        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "CASE_PACK_NOT_FOUND"
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "CASE_INPUT_INVALID"
