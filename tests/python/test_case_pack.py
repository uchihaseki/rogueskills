from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from rogueskills.api.app import create_app
from rogueskills.case_packs.finance import build_finance_case_pack
from rogueskills.contracts.case_runtime import CaseEvaluation
from rogueskills.domain.case_pack import (
    CasePackRegistrationError,
    CasePackRegistry,
    CasePackSkillError,
)
from rogueskills.domain.catalogs import SEED_SKILLS
from rogueskills.settings import Settings

from .fakes import FinanceFixtureMaterialNormalizer
from .test_finance_case import FixtureFinanceDataGateway, PassingFinanceAnalyst


def test_finance_case_pack_registers_with_declared_policy() -> None:
    pack = build_finance_case_pack(
        gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
        analyst=PassingFinanceAnalyst(),
    )
    registry = CasePackRegistry()

    registered = registry.register(pack)

    assert registered.ref == "finance-stock-analysis@1.0.0"
    assert registry.get("finance-stock-analysis") is pack
    assert registry.get("finance-stock-analysis", "1.0.0") is pack
    assert registry.descriptors() == [
        {
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
            ],
        }
    ]
    assert pack.runtime_policy.maxMutationAttempts == 1
    assert pack.runtime_policy.sourcePolicy.requiredProviderIds == [
        "sec-edgar",
        "market-price",
    ]
    assert "data.sec.gov" in pack.runtime_policy.sourcePolicy.allowedHosts

    with pytest.raises(CasePackRegistrationError, match="already registered"):
        registry.register(pack)
    with pytest.raises(CasePackRegistrationError, match="not found"):
        registry.get("missing")
    with pytest.raises(CasePackRegistrationError, match="Invalid Case Pack ID"):
        replace(pack, id="Finance")


def test_finance_case_pack_owns_skill_admission_policy() -> None:
    pack = build_finance_case_pack(
        gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
        analyst=PassingFinanceAnalyst(),
    )
    valid = {
        "status": "initial",
        "genome": {"metadata": {"category": "finance"}},
    }

    pack.validate_skill(valid)

    with pytest.raises(CasePackSkillError) as status_error:
        pack.validate_skill({**valid, "status": "quarantine"})
    assert status_error.value.reason == "status"
    with pytest.raises(CasePackSkillError) as category_error:
        pack.validate_skill(
            {"status": "initial", "genome": {"metadata": {"category": "browser"}}}
        )
    assert category_error.value.reason == "category"


def test_finance_case_pack_input_contract_is_industry_specific() -> None:
    pack = build_finance_case_pack(
        gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
        analyst=PassingFinanceAnalyst(),
    )
    assert pack.input_model is not None

    validated = pack.input_model.model_validate(
        {"ticker": "AAPL", "asOfDate": date(2026, 7, 22)}
    )

    assert validated.model_dump(mode="json") == {
        "ticker": "AAPL",
        "asOfDate": "2026-07-22",
    }
    with pytest.raises(ValidationError):
        pack.input_model.model_validate(
            {"ticker": "AAPL", "asOfDate": "2026-07-22", "url": "https://example.com"}
        )


def test_app_composition_registers_finance_case_pack(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'case-pack-app.db'}",
            project_root=Path(__file__).parents[2],
        ),
        material_normalizer=FinanceFixtureMaterialNormalizer(),
        finance_analyst=PassingFinanceAnalyst(),
        finance_data_gateway=FixtureFinanceDataGateway(),  # type: ignore[arg-type]
    )

    pack = app.state.case_pack_registry.get("finance-stock-analysis")

    assert pack.version == "1.0.0"
    assert pack.input_model is not None


@pytest.mark.asyncio
async def test_finance_case_pack_executes_existing_gateway_builder_runtime_and_evaluator() -> None:
    gateway = FixtureFinanceDataGateway()
    analyst = PassingFinanceAnalyst()
    pack = build_finance_case_pack(
        gateway=gateway,  # type: ignore[arg-type]
        analyst=analyst,
    )
    case_input = {
        "ticker": "AAPL",
        "asOfDate": "2026-07-22",
        "caseId": "case-pack-test",
        "stage": "baseline",
        "skillId": "sop-test",
        "skillVersionId": "sop-test@1",
    }

    bundle = await pack.data_gateway.fetch_live(
        case_input,
        pack.runtime_policy.sourcePolicy,
    )
    dataset = pack.dataset_builder.build(bundle, case_input)
    report = await pack.runtime.execute(
        deepcopy(SEED_SKILLS[0]),
        case_input,
        dataset,
    )
    evaluation = pack.evaluator.evaluate(report, dataset, pack.runtime_policy)

    assert gateway.calls == 1
    assert analyst.calls == 1
    assert report["caseId"] == "case-pack-test"
    assert report["stage"] == "baseline"
    assert isinstance(evaluation, CaseEvaluation)
    assert evaluation.passed is True
    assert evaluation.hardGatesPassed is True

    assert pack.mutation_planner is not None
    proposal = pack.mutation_planner.propose(deepcopy(SEED_SKILLS[0]), evaluation)
    assert proposal.id.startswith("finance-mutation-")
    assert proposal.sourceSkillVersionId == SEED_SKILLS[0]["id"]
    assert proposal.algorithmVersion == "finance-mutation-planner-v1"
