from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rogueskills.domain.case_validation import canonical_digest
from rogueskills.domain.finance_case import build_finance_dataset
from rogueskills.infrastructure.case_run_repository import CaseRunRepository
from rogueskills.infrastructure.repository import SkillRepository


class DemoFinanceReplayService:
    """Seed a compact persisted-real-data replay into the default local Demo DB."""

    CASE_ID = "case-run-demo-aapl-2026-07-21"
    CASE_PACK_ID = "finance-stock-analysis"
    CASE_PACK_VERSION = "1.0.0"
    PREFERRED_SKILL_ID = "alphaear-signal-tracker-90641e"
    FIXTURE_PATH = (
        Path(__file__).resolve().parents[1] / "domain" / "data" / "finance-demo-aapl.json"
    )

    def __init__(self, *, skills: SkillRepository, cases: CaseRunRepository) -> None:
        self.skills = skills
        self.cases = cases

    def _fixture(self) -> dict[str, Any]:
        fixture = json.loads(self.FIXTURE_PATH.read_text(encoding="utf-8"))
        if fixture.get("schemaVersion") != "demo-finance-replay-fixture-v1":
            raise ValueError("Unsupported demo Finance replay fixture schema")
        bundle = fixture.get("sourceBundle")
        if not isinstance(bundle, dict):
            raise ValueError("Demo Finance replay fixture has no source bundle")
        if canonical_digest(bundle) != fixture.get("sourceBundleDigest"):
            raise ValueError("Demo Finance replay source bundle digest mismatch")
        dataset = build_finance_dataset(bundle)
        if canonical_digest(dataset) != fixture.get("datasetDigest"):
            raise ValueError("Demo Finance replay dataset digest mismatch")
        return fixture

    def _finance_skill(self) -> dict[str, Any] | None:
        preferred = self.skills.get_skill(self.PREFERRED_SKILL_ID)
        if preferred and preferred.get("status") == "initial":
            return preferred
        return next(
            (
                skill
                for skill in self.skills.list_skills(status="initial")
                if skill.get("genome", {}).get("metadata", {}).get("category") == "finance"
            ),
            None,
        )

    def seed(self) -> dict[str, Any]:
        fixture = self._fixture()
        bundle = fixture["sourceBundle"]
        existing = self.cases.get(self.CASE_ID, include_bundle=True)
        if (
            existing
            and canonical_digest(existing.get("_sourceBundle")) == fixture["sourceBundleDigest"]
        ):
            return {"caseRun": existing, "action": "reused", "fixture": fixture}

        skill = self._finance_skill()
        if skill is None:
            return {"caseRun": None, "action": "skipped_no_finance_skill", "fixture": fixture}

        captured_at = str(fixture.get("capturedAt") or datetime.now(UTC).isoformat())
        case_input = dict(fixture["input"])
        state: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "id": self.CASE_ID,
            "casePackId": self.CASE_PACK_ID,
            "casePackVersion": self.CASE_PACK_VERSION,
            "input": case_input,
            "ticker": case_input["ticker"],
            "asOfDate": case_input["asOfDate"],
            "mode": fixture["sourceMode"],
            "replayCaseId": None,
            "skillId": skill["id"],
            "baseSkillVersionId": skill["currentVersionId"],
            "runtimePresetId": None,
            "evolvedSkillVersionId": None,
            "status": "succeeded",
            "phase": "completed",
            "runtimeVerified": False,
            "baseline": None,
            "mutation": None,
            "evolved": None,
            "comparison": None,
            "finalReport": None,
            "finalEvaluation": None,
            "runtimeArtifact": None,
            "caseLabel": fixture["displayName"],
            "caseDescription": fixture["description"],
            "demoIncluded": True,
            "sourceCaseId": fixture["sourceCaseId"],
            "sourceBundleDigest": fixture["sourceBundleDigest"],
            "datasetDigest": fixture["datasetDigest"],
            "sourceVerification": fixture["originalRuntimeVerification"],
            "createdAt": captured_at,
            "completedAt": captured_at,
            "error": None,
        }
        if existing:
            state["revision"] = existing["revision"]
        saved = self.cases.save(
            state,
            source_bundle=bundle,
            expected_revision=existing["revision"] if existing else None,
        )
        return {
            "caseRun": saved,
            "action": "updated" if existing else "created",
            "fixture": fixture,
        }
