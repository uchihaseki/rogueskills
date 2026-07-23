from __future__ import annotations

from datetime import date
from typing import Any

from rogueskills.adapters.finance_data import SecFinanceDataGateway
from rogueskills.agents.case_runtime import RuntimeArtifactBuilder
from rogueskills.agents.finance_analyst import FinanceAnalyst
from rogueskills.application.errors import ApplicationError
from rogueskills.contracts.case_runtime import (
    CaseEvaluation,
    CaseMutationProposal,
    CaseRuntimePolicy,
    CaseSkillPolicy,
    CaseSourcePolicy,
)
from rogueskills.contracts.finance_case import FinanceCaseInput
from rogueskills.domain.case_pack import CasePack
from rogueskills.domain.finance_case import (
    build_finance_dataset,
    build_finance_report,
    evaluate_finance_report,
    plan_finance_mutation,
)


class FinanceCaseDataGateway:
    def __init__(self, gateway: SecFinanceDataGateway) -> None:
        self.gateway = gateway

    async def fetch_live(
        self, case_input: dict[str, Any], source_policy: CaseSourcePolicy
    ) -> dict[str, Any]:
        del source_policy
        return await self.gateway.fetch_bundle(
            ticker=str(case_input["ticker"]),
            as_of_date=date.fromisoformat(str(case_input["asOfDate"])),
        )

    def validate_replay(self, source_bundle: dict[str, Any], case_input: dict[str, Any]) -> None:
        expected = str(case_input["ticker"]).upper()
        actual = str(source_bundle.get("company", {}).get("ticker") or "").upper()
        if actual != expected:
            raise ApplicationError(
                "REPLAY_TICKER_MISMATCH",
                "重放快照的 ticker 与请求不一致。",
                status_code=409,
            )


class FinanceDatasetBuilder:
    def build(
        self, source_bundle: dict[str, Any], case_input: dict[str, Any]
    ) -> dict[str, Any]:
        del case_input
        return build_finance_dataset(source_bundle)


class FinanceCaseRuntime:
    def __init__(self, analyst: FinanceAnalyst) -> None:
        self.analyst = analyst

    async def execute(
        self,
        genome: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        narrative = await self.analyst.analyze(
            genome=genome,
            case=case_input,
            dataset=dataset,
            feedback=feedback,
        )
        return build_finance_report(
            case_id=str(case_input["caseId"]),
            stage=str(case_input["stage"]),
            skill_id=str(case_input["skillId"]),
            skill_version_id=str(case_input["skillVersionId"]),
            dataset=dataset,
            narrative=narrative,
        )


class FinanceCaseEvaluator:
    def evaluate(
        self,
        report: dict[str, Any],
        dataset: dict[str, Any],
        policy: CaseRuntimePolicy,
    ) -> CaseEvaluation:
        del dataset, policy
        return CaseEvaluation.model_validate(evaluate_finance_report(report))


class FinanceCaseMutationPlanner:
    def propose(
        self,
        genome: dict[str, Any],
        evaluation: CaseEvaluation,
    ) -> CaseMutationProposal:
        proposal = plan_finance_mutation(genome, evaluation.model_dump(mode="json"))
        return CaseMutationProposal(
            id=str(proposal["id"]),
            sourceSkillVersionId=str(genome.get("id") or "unknown"),
            name=str(proposal.get("name") or "Case Runtime Mutation"),
            reason=str(proposal["reason"]),
            evidenceRefs=[str(item) for item in proposal.get("evidenceRefs", [])],
            tradeoff=str(proposal["tradeoff"]),
            tags=[str(item) for item in proposal.get("tags", [])],
            genomePatch=list(proposal.get("genomePatch", [])),
            algorithmVersion=str(proposal["algorithmVersion"]),
        )


def build_finance_case_pack(
    *,
    gateway: SecFinanceDataGateway,
    analyst: FinanceAnalyst,
    artifact_builder: RuntimeArtifactBuilder | None = None,
) -> CasePack:
    def preflight() -> dict[str, Any]:
        info = analyst.info
        return {
            "ready": info.configured,
            "analyst": {
                "mode": info.mode,
                "provider": info.provider,
                "model": info.model,
                "configured": info.configured,
            },
            "sources": [
                {
                    "id": "sec-edgar",
                    "name": "SEC EDGAR",
                    "configured": True,
                    "reachable": None,
                    "state": "checked_on_run",
                },
                {
                    "id": "stooq",
                    "name": "Stooq daily price",
                    "configured": True,
                    "reachable": None,
                    "state": "checked_on_run",
                },
            ],
            "runtime": "real-finance-case-v1",
        }

    return CasePack(
        id="finance-stock-analysis",
        version="1.0.0",
        name="Public Company Financial Analysis",
        description="Evidence-bound public-company analysis using filings and dated market data.",
        input_model=FinanceCaseInput,
        report_model=None,
        capabilities=("live", "verified_replay", "auto_evolve", "runtime_artifact"),
        skill_policy=CaseSkillPolicy(requiredStatus="initial", requiredCategory="finance"),
        runtime_policy=CaseRuntimePolicy(
            maxMutationAttempts=1,
            timeoutMs=180_000,
            refreshOnFailedCaseIds=["source-integrity", "valuation-sensitivity"],
            sourcePolicy=CaseSourcePolicy(
                requiredProviderIds=["sec-edgar", "market-price"],
                allowedHosts=[
                    "www.sec.gov",
                    "data.sec.gov",
                    "stooq.com",
                    "query1.finance.yahoo.com",
                ],
                maxSnapshots=8,
            ),
        ),
        data_gateway=FinanceCaseDataGateway(gateway),
        dataset_builder=FinanceDatasetBuilder(),
        runtime=FinanceCaseRuntime(analyst),
        evaluator=FinanceCaseEvaluator(),
        mutation_planner=FinanceCaseMutationPlanner(),
        artifact_builder=artifact_builder,
        state_projector=lambda case_input: {
            "ticker": str(case_input["ticker"]).upper(),
            "asOfDate": str(case_input["asOfDate"]),
            "financeEvolutionRunId": None,
            "agentPreset": None,
        },
        preflight_provider=preflight,
    )
