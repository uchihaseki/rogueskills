from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import inspect, select

from rogueskills.domain.catalogs import SEED_SKILLS
from rogueskills.infrastructure.case_run_repository import (
    CaseRunRepository,
    StaleCaseRunRevision,
)
from rogueskills.infrastructure.case_store import CompatibleCaseRunStore
from rogueskills.infrastructure.database import CaseRunRow, create_database
from rogueskills.infrastructure.finance_case_repository import FinanceCaseRepository
from rogueskills.infrastructure.repository import SkillRepository


def _state(case_id: str = "generic-case-test") -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "id": case_id,
        "casePackId": "generic-case",
        "casePackVersion": "1.0.0",
        "input": {"value": 7},
        "mode": "live",
        "replayCaseId": None,
        "skillId": "browser-extraction-base",
        "baseSkillVersionId": "browser-extraction-base@1",
        "evolvedSkillVersionId": None,
        "status": "running",
        "phase": "acquiring_sources",
        "runtimeVerified": False,
        "createdAt": "2026-07-23T00:00:00Z",
        "completedAt": None,
        "error": None,
    }


def _repositories(tmp_path: Path) -> tuple[CaseRunRepository, FinanceCaseRepository, object]:
    engine, sessions = create_database(f"sqlite:///{tmp_path / 'case-runs.db'}")
    skills = SkillRepository(sessions)
    skills.save_skill(deepcopy(SEED_SKILLS[0]), source_id="seed", trusted_status=True)
    return CaseRunRepository(sessions), FinanceCaseRepository(sessions), (engine, sessions)


def test_case_run_repository_persists_revision_and_source_bundle(tmp_path: Path) -> None:
    repository, _legacy, resources = _repositories(tmp_path)
    engine, sessions = resources
    state = _state()

    created = repository.save(state, source_bundle={"source": "live"})
    state["phase"] = "completed"
    state["status"] = "succeeded"
    state["completedAt"] = "2026-07-23T00:01:00Z"
    updated = repository.save(state, expected_revision=created["revision"])
    loaded = repository.get(str(state["id"]), include_bundle=True)

    assert created["revision"] == 1
    assert updated["revision"] == 2
    assert loaded is not None
    assert loaded["revision"] == 2
    assert loaded["phase"] == "completed"
    assert loaded["_sourceBundle"] == {"source": "live"}
    with sessions() as session:
        row = session.scalar(select(CaseRunRow).where(CaseRunRow.id == state["id"]))
        assert row is not None
        assert row.case_pack_id == "generic-case"
        assert row.completed_at is not None
    assert "case_runs" in inspect(engine).get_table_names()
    engine.dispose()


def test_case_run_repository_rejects_stale_revision(tmp_path: Path) -> None:
    repository, _legacy, resources = _repositories(tmp_path)
    engine, _sessions = resources
    state = _state()
    repository.save(state)

    with pytest.raises(StaleCaseRunRevision, match="Expected"):
        repository.save(state, expected_revision=0)
    engine.dispose()


def test_compatible_store_reads_legacy_finance_without_copying_it(tmp_path: Path) -> None:
    repository, legacy, resources = _repositories(tmp_path)
    engine, _sessions = resources
    legacy_state = {
        **_state("finance-case-legacy"),
        "ticker": "AAPL",
        "asOfDate": "2026-07-21",
        "casePackId": "finance-stock-analysis",
    }
    legacy.save(legacy_state, source_bundle={"company": {"ticker": "AAPL"}})
    store = CompatibleCaseRunStore(repository, legacy)

    loaded = store.get("finance-case-legacy", include_bundle=True)

    assert loaded is not None
    assert loaded["ticker"] == "AAPL"
    assert loaded["_sourceBundle"]["company"]["ticker"] == "AAPL"
    assert repository.get("finance-case-legacy") is None
    assert [item["id"] for item in store.list(case_pack_id="finance-stock-analysis")] == [
        "finance-case-legacy"
    ]
    engine.dispose()
