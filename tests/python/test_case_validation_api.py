from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rogueskills.agents.finance_analyst import FinanceAnalystInfo
from rogueskills.api.app import create_app
from rogueskills.application.errors import ApplicationError
from rogueskills.contracts.finance_case import FinanceNarrative
from rogueskills.infrastructure.database import AgentPresetRow
from rogueskills.settings import Settings

from .fakes import FinanceFixtureMaterialNormalizer
from .test_finance_case import FixtureFinanceDataGateway, _finance_skill


class CandidateAwareFinanceAnalyst:
    def __init__(self, outcome: str = "improves") -> None:
        self.calls: list[dict[str, Any]] = []
        self.outcome = outcome
        self.model = "candidate-aware-finance"

    @property
    def info(self) -> FinanceAnalystInfo:
        return FinanceAnalystInfo(
            mode="replay-fixture",
            provider="fixture",
            model=self.model,
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
        del genome, dataset
        candidate = agent_config is not None
        self.calls.append(
            {
                "candidate": candidate,
                "feedback": feedback,
                "presetId": agent_config.get("presetId") if agent_config else None,
                "executionKind": case.get("executionKind"),
                "executionPolicy": deepcopy(case.get("executionPolicy")),
                "presetExecutionPolicy": deepcopy(
                    agent_config.get("executionPolicy") if agent_config else None
                ),
            }
        )
        if self.outcome == "candidate_error" and candidate:
            raise RuntimeError("candidate runtime exploded")
        evidence_bound = self.outcome == "no_improvement" or (
            self.outcome == "improves" and candidate
        )
        evidence = (
            [
                "fact-revenue-annual_current",
                "fact-net_income-annual_current",
                "metric-free-cash-flow",
            ]
            if evidence_bound
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


def _victory_run_with_preset(app: Any, api: TestClient, skill: dict[str, Any]) -> dict[str, Any]:
    created = api.post(
        "/api/runs",
        json={"seed": "CASE-VALIDATION-001", "skillId": skill["id"], "modeId": "stable"},
    )
    assert created.status_code == 201
    record = created.json()
    state = record["run"]
    state.update(
        {
            "status": "victory",
            "phase": "ended",
            "mutationIds": [
                "source_triangulation",
                "filing_recency_guard",
                "accounting_normalizer",
                "earnings_quality_check",
                "valuation_sensitivity",
                "risk_register",
            ],
            "evolutionIds": [
                "evidence_grade_analyst",
                "scenario_valuation_engine",
                "risk_governed_research",
            ],
        }
    )
    saved = app.state.repository.save_run(
        state,
        base_skill_version_id=record["baseSkillVersionId"],
        expected_revision=record["revision"],
    )
    preset = api.post(
        f"/api/runs/{state['id']}/agent-preset",
        json={
            "expectedRevision": saved["revision"],
            "projectName": "AAPL Candidate Agent",
            "projectDescription": "Validate the browser-produced finance candidate.",
            "scenario": "public-company-financial-analysis",
        },
    )
    assert preset.status_code == 201
    return {**saved, "artifact": preset.json()["preset"]}


def _wait_for_validation(api: TestClient, validation_id: str) -> dict[str, Any]:
    for _ in range(100):
        response = api.get(f"/api/case-validations/{validation_id}")
        assert response.status_code == 200
        validation = response.json()["validation"]
        if validation["status"] in {"succeeded", "failed"}:
            return validation
        time.sleep(0.01)
    raise AssertionError("CaseValidation did not finish")


def _prepare_validation(
    app: Any,
    api: TestClient,
    *,
    gateway: FixtureFinanceDataGateway | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any]:
    skill = _finance_skill(api)
    source = api.post(
        "/api/case-runs",
        json={
            "casePackId": "finance-stock-analysis",
            "casePackVersion": "1.0.0",
            "skillId": skill["id"],
            "skillVersionId": skill["currentVersionId"],
            "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
            "mode": "live",
            "autoEvolve": False,
        },
    )
    assert source.status_code == 201
    if gateway is not None:
        assert gateway.calls == 1
    source_case = source.json()["caseRun"]
    run = _victory_run_with_preset(app, api, skill)
    pack = app.state.case_pack_registry.get("finance-stock-analysis", "1.0.0")
    return skill, source_case, run, pack


def _create_validation_state(
    app: Any,
    *,
    run: dict[str, Any],
    source_case: dict[str, Any],
    pack: Any,
) -> dict[str, Any]:
    state, created = app.state.case_validation_service.create(
        run_id=run["run"]["id"],
        pack=pack,
        replay_case_id=source_case["id"],
        case_input={"ticker": "AAPL", "asOfDate": "2026-07-22"},
    )
    assert created is True
    return state


def test_evolution_candidate_runs_same_source_validation_and_promotes(tmp_path: Path) -> None:
    analyst = CandidateAwareFinanceAnalyst()
    gateway = FixtureFinanceDataGateway()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'case-validation.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=gateway,  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill = _finance_skill(api)
        source = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": skill["id"],
                "skillVersionId": skill["currentVersionId"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "live",
                "autoEvolve": False,
            },
        )
        assert source.status_code == 201
        source_case = source.json()["caseRun"]
        run = _victory_run_with_preset(app, api, skill)

        options = api.get(
            f"/api/runs/{run['run']['id']}/case-validation-options"
            "?casePackId=finance-stock-analysis"
        )
        assert options.status_code == 200
        selected_option = next(
            item for item in options.json()["options"] if item["caseId"] == source_case["id"]
        )
        assert selected_option["mode"] == "verified_replay"
        assert selected_option["sourceMode"] == "live"

        created = api.post(
            f"/api/runs/{run['run']['id']}/case-validations",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
            },
        )
        assert created.status_code == 202
        validation = _wait_for_validation(api, created.json()["validation"]["id"])

        assert validation["status"] == "succeeded"
        assert validation["baseline"]["evaluation"]["score"] == 88.0
        assert validation["candidate"]["evaluation"]["score"] == 100.0
        assert validation["comparison"]["scoreDelta"] == 12.0
        assert validation["comparison"]["repairedCaseIds"] == ["claim-citations"]
        assert validation["runtimeVerified"] is True
        assert validation["accepted"] is True
        assert validation["promotion"]["status"] == "created"
        assert validation["promotion"]["promoted"] is True
        assert validation["sourceBundleDigest"].startswith("sha256:")
        assert validation["datasetDigest"].startswith("sha256:")
        assert validation["executionPolicyDigest"].startswith("sha256:")
        assert analyst.calls[-2]["candidate"] is False
        assert analyst.calls[-2]["feedback"] is None
        assert analyst.calls[-2]["executionKind"] == "skill_version"
        assert analyst.calls[-1]["candidate"] is True
        assert analyst.calls[-1]["feedback"] is None
        assert analyst.calls[-1]["executionKind"] == "agent_preset"
        assert analyst.calls[-2]["executionPolicy"] == analyst.calls[-1]["executionPolicy"]
        assert analyst.calls[-1]["presetExecutionPolicy"] == analyst.calls[-1]["executionPolicy"]
        assert gateway.calls == 1

        promoted = api.get(
            f"/api/skill-versions/{validation['promotion']['evolvedSkillVersionId']}"
        )
        assert promoted.status_code == 200
        genome = promoted.json()["version"]["genome"]
        assert genome["runtimeBinding"]["presetId"] == run["artifact"]["id"]
        assert genome["runtimeBinding"]["presetDigest"] == run["artifact"]["digest"]
        assert genome["runtimeVerification"]["caseId"] == source_case["id"]

        bound_run = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": skill["id"],
                "skillVersionId": validation["promotion"]["evolvedSkillVersionId"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "autoEvolve": False,
            },
        )
        assert bound_run.status_code == 201
        assert bound_run.json()["caseRun"]["runtimePresetId"] == run["artifact"]["id"]
        assert analyst.calls[-1]["candidate"] is True

        bound_auto_evolve = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": skill["id"],
                "skillVersionId": validation["promotion"]["evolvedSkillVersionId"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "autoEvolve": True,
            },
        )
        assert bound_auto_evolve.status_code == 409
        assert bound_auto_evolve.json()["error"]["code"] == "BOUND_PRESET_CANNOT_AUTO_EVOLVE"

        duplicate = api.post(
            f"/api/runs/{run['run']['id']}/case-validations",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
            },
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["created"] is False
        assert duplicate.json()["validation"]["id"] == validation["id"]

        demo_context = api.get("/api/demo/context")
        assert demo_context.status_code == 200
        context = demo_context.json()
        assert context["caseValidation"]["id"] == validation["id"]
        assert context["promotion"]["status"] == "created"
        assert context["nodeHistorySummary"]["saveVersion"] == 3
        assert context["demoScript"]["attributionBoundary"].startswith("节点优化项")

        with app.state.preset_repository.sessions.begin() as session:
            row = session.get(AgentPresetRow, run["artifact"]["id"])
            assert row is not None
            corrupted_preset = json.loads(row.config_json)
            corrupted_preset["digest"] = "sha256:" + "f" * 64
            row.config_json = json.dumps(corrupted_preset)
        bound_with_corrupted_preset = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": skill["id"],
                "skillVersionId": validation["promotion"]["evolvedSkillVersionId"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "autoEvolve": False,
            },
        )
        assert bound_with_corrupted_preset.status_code == 409
        assert bound_with_corrupted_preset.json()["error"]["code"] == (
            "BOUND_PRESET_INTEGRITY_FAILED"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_verified"),
    [("hard_gate_failure", False), ("no_improvement", True)],
)
async def test_candidate_must_pass_hard_gates_and_strictly_improve(
    tmp_path: Path, outcome: str, expected_verified: bool
) -> None:
    analyst = CandidateAwareFinanceAnalyst(outcome)
    gateway = FixtureFinanceDataGateway()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / f'{outcome}.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=gateway,  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        _skill, source_case, run, pack = _prepare_validation(app, api, gateway=gateway)
        state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        validation = await app.state.case_validation_service.execute(state["id"], pack=pack)

        assert validation["runtimeVerified"] is expected_verified
        assert validation["accepted"] is False
        assert validation["promotion"]["status"] == "not_eligible"
        assert validation["promotion"]["promoted"] is False
        assert gateway.calls == 1
        if outcome == "no_improvement":
            assert validation["comparison"]["scoreDelta"] == 0
            assert validation["comparison"]["candidateHardGatesPassed"] is True
        else:
            assert validation["comparison"]["candidateHardGatesPassed"] is False


@pytest.mark.asyncio
async def test_validation_detects_source_and_execution_policy_drift(tmp_path: Path) -> None:
    analyst = CandidateAwareFinanceAnalyst()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'drift.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        _skill, source_case, run, pack = _prepare_validation(app, api)
        source_state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        stored = app.state.case_run_repository.get(source_case["id"], include_bundle=True)
        assert stored is not None
        changed_bundle = deepcopy(stored.pop("_sourceBundle"))
        changed_bundle["company"]["name"] = "Changed after validation creation"
        app.state.case_run_repository.save(
            stored,
            source_bundle=changed_bundle,
            expected_revision=stored["revision"],
        )
        with pytest.raises(ApplicationError) as source_error:
            await app.state.case_validation_service.execute(source_state["id"], pack=pack)
        assert source_error.value.code == "REPLAY_SOURCE_BUNDLE_CHANGED"
        assert app.state.case_validation_service.get(source_state["id"])["status"] == "failed"

        # Restore the source, create a new idempotency scope, then change the Analyst model.
        original_bundle = deepcopy(changed_bundle)
        original_bundle["company"]["name"] = "Apple Inc."
        current = app.state.case_run_repository.get(source_case["id"])
        assert current is not None
        app.state.case_run_repository.save(
            current,
            source_bundle=original_bundle,
            expected_revision=current["revision"],
        )
        analyst.model = "model-at-policy-create"
        policy_state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        analyst.model = "different-model-after-create"
        with pytest.raises(ApplicationError) as policy_error:
            await app.state.case_validation_service.execute(policy_state["id"], pack=pack)
        assert policy_error.value.code == "CASE_VALIDATION_EXECUTION_POLICY_CHANGED"


@pytest.mark.asyncio
async def test_version_conflict_and_completed_promotion_recovery(tmp_path: Path) -> None:
    analyst = CandidateAwareFinanceAnalyst()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'promotion-recovery.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        skill, source_case, run, pack = _prepare_validation(app, api)
        conflict_state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        changed = deepcopy(app.state.repository.get_skill(skill["id"])["genome"])
        changed["description"] += " Concurrent version."
        app.state.repository.save_skill(changed, source_id="test", trusted_status=True)
        conflict = await app.state.case_validation_service.execute(conflict_state["id"], pack=pack)
        assert conflict["accepted"] is True
        assert conflict["promotion"]["status"] == "version_conflict"
        assert conflict["promotion"]["promoted"] is False

        # Use a fresh Skill lineage so the successful promotion can be replayed as a worker restart.
        second_genome = deepcopy(skill["genome"])
        second_genome.update(
            {
                "id": f"{skill['id']}-recovery",
                "name": "Promotion Recovery Finance Skill",
                "status": "quarantine",
            }
        )
        stored = api.post(
            "/api/skills", json={"genome": second_genome, "sourceId": "test-recovery"}
        ).json()["skill"]
        benchmark = api.post(f"/api/skills/{stored['id']}/benchmark", json={}).json()
        promoted = api.post(
            f"/api/skills/{stored['id']}/promote",
            json={
                "evaluationId": benchmark["evaluation"]["id"],
                "expectedSkillVersionId": stored["currentVersionId"],
            },
        )
        assert promoted.status_code == 200
        second_skill = promoted.json()["skill"]
        second_source = api.post(
            "/api/case-runs",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "skillId": second_skill["id"],
                "skillVersionId": second_skill["currentVersionId"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-22"},
                "mode": "live",
                "autoEvolve": False,
            },
        ).json()["caseRun"]
        second_run = _victory_run_with_preset(app, api, second_skill)
        recovery_state = _create_validation_state(
            app, run=second_run, source_case=second_source, pack=pack
        )
        completed = await app.state.case_validation_service.execute(recovery_state["id"], pack=pack)
        promoted_version = completed["promotion"]["evolvedSkillVersionId"]
        version_count = len(app.state.repository.get_skill(second_skill["id"])["versions"])
        interrupted = deepcopy(completed)
        interrupted.update({"status": "running", "phase": "promoting", "completedAt": None})
        interrupted["promotion"] = {
            "status": "pending",
            "promoted": False,
            "evolvedSkillVersionId": None,
            "currentSkillVersionId": second_skill["currentVersionId"],
            "error": None,
        }
        app.state.case_validation_repository.save(interrupted)
        recovered = await app.state.case_validation_service.execute(recovery_state["id"], pack=pack)
        assert recovered["promotion"]["status"] == "created"
        assert recovered["promotion"]["evolvedSkillVersionId"] == promoted_version
        assert len(app.state.repository.get_skill(second_skill["id"])["versions"]) == version_count


@pytest.mark.asyncio
async def test_unexpected_candidate_error_persists_partial_evidence(tmp_path: Path) -> None:
    analyst = CandidateAwareFinanceAnalyst("candidate_error")
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'unexpected.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=analyst,
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        _skill, source_case, run, pack = _prepare_validation(app, api)
        state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        with pytest.raises(ApplicationError) as caught:
            await app.state.case_validation_service.execute(state["id"], pack=pack)
        assert caught.value.code == "CASE_VALIDATION_EXECUTION_FAILED"
        failed = app.state.case_validation_service.get(state["id"])
        assert failed["status"] == "failed"
        assert failed["phase"] == "failed"
        assert failed["baseline"] is not None
        assert failed["candidate"] is None
        assert failed["error"]["details"]["errorType"] == "RuntimeError"

        retried, created = app.state.case_validation_service.create(
            run_id=run["run"]["id"],
            pack=pack,
            replay_case_id=source_case["id"],
            case_input={"ticker": "AAPL", "asOfDate": "2026-07-22"},
            retry_failed=True,
        )
        assert created is True
        assert retried["id"] != failed["id"]
        assert retried["retryOfValidationId"] == failed["id"]
        assert retried["retryCount"] == 1
        with pytest.raises(ApplicationError):
            await app.state.case_validation_service.execute(retried["id"], pack=pack)
        second_failure = app.state.case_validation_service.get(retried["id"])

        analyst.outcome = "improves"
        second_retry, created = app.state.case_validation_service.create(
            run_id=run["run"]["id"],
            pack=pack,
            replay_case_id=source_case["id"],
            case_input={"ticker": "AAPL", "asOfDate": "2026-07-22"},
            retry_failed=True,
        )
        assert created is True
        assert second_retry["retryOfValidationId"] == second_failure["id"]
        assert second_retry["retryCount"] == 2
        completed = await app.state.case_validation_service.execute(
            second_retry["id"], pack=pack
        )
        assert completed["status"] == "succeeded"
        assert completed["candidate"]["evaluation"]["score"] == 100.0


@pytest.mark.asyncio
async def test_validation_rejects_preset_digest_and_run_lineage_mismatch(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'integrity.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=CandidateAwareFinanceAnalyst(),
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        _skill, source_case, run, pack = _prepare_validation(app, api)
        state = _create_validation_state(app, run=run, source_case=source_case, pack=pack)
        corrupted = deepcopy(state)
        corrupted["candidatePresetDigest"] = "sha256:" + "f" * 64
        app.state.case_validation_repository.save(corrupted)
        with pytest.raises(ApplicationError) as digest_error:
            await app.state.case_validation_service.execute(state["id"], pack=pack)
        assert digest_error.value.code == "AGENT_PRESET_INTEGRITY_FAILED"

        run_record = app.state.repository.get_run(run["run"]["id"])
        assert run_record is not None
        mismatched_run = deepcopy(run_record["run"])
        mismatched_run["baseSkillId"] = "different-skill-lineage"
        app.state.repository.save_run(
            mismatched_run,
            base_skill_version_id=run_record["baseSkillVersionId"],
            expected_revision=run_record["revision"],
        )
        with pytest.raises(ApplicationError) as lineage_error:
            app.state.case_validation_service.create(
                run_id=run["run"]["id"],
                pack=pack,
                replay_case_id=source_case["id"],
                case_input={"ticker": "AAPL", "asOfDate": "2026-07-22"},
            )
        assert lineage_error.value.code == "AGENT_PRESET_LINEAGE_MISMATCH"


def test_replay_as_of_date_mismatch_is_rejected_before_execution(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'date-mismatch.db'}",
            project_root=Path(__file__).parents[2],
            automatic_run_step_delay_seconds=0,
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=CandidateAwareFinanceAnalyst(),
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )
    with TestClient(app) as api:
        _skill, source_case, run, _pack = _prepare_validation(app, api)
        response = api.post(
            f"/api/runs/{run['run']['id']}/case-validations",
            json={
                "casePackId": "finance-stock-analysis",
                "casePackVersion": "1.0.0",
                "mode": "verified_replay",
                "replayCaseId": source_case["id"],
                "input": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "REPLAY_AS_OF_DATE_MISMATCH"
