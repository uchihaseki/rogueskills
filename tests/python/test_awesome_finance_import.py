from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rogueskills.api.app import create_app
from rogueskills.settings import Settings

SKILL = """---
name: alphaear-demo
description: A finance workflow for evidence-bound company analysis.
---

# AlphaEar Demo

## Goal
Produce a structured equity research note from public filings.

## Steps
1. Collect public filings and dated market data.
2. Compare revenue, cash flow, and valuation assumptions.
3. Return a report with evidence, risks, and data gaps.

## Constraints
- Never fabricate financial figures or sources.
- Do not issue personalized investment advice.

## Inputs
- Ticker and as-of date

## Outputs
- Evidence-bound research report
"""


def _settings(root: Path) -> Settings:
    return Settings(
        database_url="sqlite://",
        project_root=root,
        automatic_run_step_delay_seconds=0,
    )


def _write_source(root: Path, *, license_text: str = "Apache License, Version 2.0") -> None:
    skill_path = root / "Awesome-finance-skills" / "skills" / "alphaear-demo" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(SKILL, encoding="utf-8")
    (root / "Awesome-finance-skills" / "LICENSE").write_text(license_text, encoding="utf-8")


def test_imports_local_awesome_finance_skills_through_admission_and_is_idempotent(
    tmp_path: Path,
) -> None:
    _write_source(tmp_path)
    with TestClient(create_app(_settings(tmp_path))) as api:
        imported = api.post("/api/scenarios/finance/import-awesome", json={})
        assert imported.status_code == 200
        payload = imported.json()
        assert payload["source"]["license"] == "Apache-2.0"
        assert payload["summary"] == {
            "discovered": 1,
            "processed": 1,
            "initialSkills": 1,
            "reused": 0,
            "promoted": 1,
            "rejected": 0,
        }
        item = payload["skills"][0]
        assert item["sourceName"] == "alphaear-demo"
        assert item["status"] == "initial"
        assert item["evaluation"]["benchmarkId"] == "library-admission-v1"

        library = api.get("/api/library/initial").json()["skills"]
        imported_skill = next(
            item for item in library if item["id"] == payload["initialSkillIds"][0]
        )
        assert imported_skill["sourceId"] == "awesome-finance-skills"
        assert imported_skill["genome"]["metadata"]["category"] == "finance"
        assert "awesome-finance-skills" in imported_skill["genome"]["metadata"]["tags"]

        repeated = api.post("/api/scenarios/finance/import-awesome", json={})
        assert repeated.status_code == 200
        assert repeated.json()["summary"] == {
            "discovered": 1,
            "processed": 1,
            "initialSkills": 1,
            "reused": 1,
            "promoted": 0,
            "rejected": 0,
        }
        assert (
            len(
                [
                    item
                    for item in api.get("/api/skills").json()["skills"]
                    if item["sourceId"] == "awesome-finance-skills"
                ]
            )
            == 1
        )


def test_unknown_source_license_is_kept_out_of_initial_library(tmp_path: Path) -> None:
    _write_source(tmp_path, license_text="unidentified license")
    with TestClient(create_app(_settings(tmp_path))) as api:
        imported = api.post("/api/scenarios/finance/import-awesome", json={})
        assert imported.status_code == 200
        payload = imported.json()
        assert payload["source"]["license"] == "unknown"
        assert payload["summary"]["initialSkills"] == 0
        assert payload["skills"][0]["status"] == "quarantine"
        assert payload["skills"][0]["evaluation"]["passed"] is False


def test_quarantine_import_can_be_promoted_on_a_later_idempotent_run(tmp_path: Path) -> None:
    _write_source(tmp_path)
    with TestClient(create_app(_settings(tmp_path))) as api:
        first = api.post(
            "/api/scenarios/finance/import-awesome",
            json={"autoPromote": False},
        )
        assert first.status_code == 200
        assert first.json()["skills"][0]["status"] == "quarantine"

        second = api.post(
            "/api/scenarios/finance/import-awesome",
            json={"autoPromote": True},
        )
        assert second.status_code == 200
        assert second.json()["skills"][0]["status"] == "initial"
        assert second.json()["skills"][0]["action"] == "promoted"


def test_default_demo_database_auto_seeds_awesome_finance_skills(tmp_path: Path) -> None:
    _write_source(tmp_path)
    database = tmp_path / "data" / "rogueskills.db"
    settings = Settings(database_url=f"sqlite:///{database}", project_root=tmp_path)
    with TestClient(create_app(settings)) as api:
        initial = api.get("/api/library/initial")
        assert initial.status_code == 200
        imported = [
            item
            for item in initial.json()["skills"]
            if item["sourceId"] == "awesome-finance-skills"
        ]
        assert len(imported) == 1
        assert imported[0]["name"] == "alphaear-demo"
        assert imported[0]["status"] == "initial"
