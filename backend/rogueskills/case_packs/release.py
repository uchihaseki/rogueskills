from __future__ import annotations

from typing import Any

from rogueskills.adapters.github_release_data import GithubReleaseReadinessGateway
from rogueskills.agents.case_runtime import RuntimeArtifactBuilder
from rogueskills.contracts.case_runtime import (
    CaseEvaluation,
    CaseMutationProposal,
    CaseRuntimePolicy,
    CaseSkillPolicy,
    CaseSourcePolicy,
)
from rogueskills.contracts.release_case import (
    ReleaseReadinessInput,
    ReleaseReadinessReport,
)
from rogueskills.domain.case_pack import CasePack
from rogueskills.domain.release_case import (
    build_release_dataset,
    build_release_report,
    evaluate_release_report,
    plan_release_mutation,
    release_evidence_workflow_enabled,
)


class ReleaseDatasetBuilder:
    def build(
        self, source_bundle: dict[str, Any], case_input: dict[str, Any]
    ) -> dict[str, Any]:
        return build_release_dataset(source_bundle, case_input)


class ReleaseReadinessRuntime:
    async def execute(
        self,
        genome: dict[str, Any],
        case_input: dict[str, Any],
        dataset: dict[str, Any],
        feedback: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        del feedback
        return build_release_report(
            case_input=case_input,
            dataset=dataset,
            evidence_workflow_enabled=release_evidence_workflow_enabled(genome),
        )


class ReleaseReadinessEvaluator:
    def evaluate(
        self,
        report: dict[str, Any],
        dataset: dict[str, Any],
        policy: CaseRuntimePolicy,
    ) -> CaseEvaluation:
        del policy
        return evaluate_release_report(report, dataset)


class ReleaseReadinessMutationPlanner:
    def propose(
        self, genome: dict[str, Any], evaluation: CaseEvaluation
    ) -> CaseMutationProposal:
        return plan_release_mutation(genome, evaluation)


def build_release_readiness_case_pack(
    *,
    gateway: GithubReleaseReadinessGateway,
    artifact_builder: RuntimeArtifactBuilder | None = None,
) -> CasePack:
    return CasePack(
        id="release-readiness",
        version="1.0.0",
        name="GitHub Release Readiness",
        description=(
            "Evidence-bound release readiness using candidate commits, check runs, and open "
            "pull-request state from GitHub."
        ),
        input_model=ReleaseReadinessInput,
        report_model=ReleaseReadinessReport,
        capabilities=("live", "verified_replay", "auto_evolve", "runtime_artifact"),
        skill_policy=CaseSkillPolicy(requiredStatus="initial", requiredCategory="release"),
        runtime_policy=CaseRuntimePolicy(
            maxMutationAttempts=1,
            timeoutMs=120_000,
            refreshOnFailedCaseIds=[],
            sourcePolicy=CaseSourcePolicy(
                requiredProviderIds=["github-api"],
                allowedHosts=["api.github.com"],
                maxSnapshots=4,
            ),
        ),
        data_gateway=gateway,
        dataset_builder=ReleaseDatasetBuilder(),
        runtime=ReleaseReadinessRuntime(),
        preset_runtime=None,
        evaluator=ReleaseReadinessEvaluator(),
        mutation_planner=ReleaseReadinessMutationPlanner(),
        artifact_builder=artifact_builder,
        state_projector=lambda case_input: {
            "repository": str(case_input["repository"]),
            "ref": str(case_input["ref"]),
            "baseBranch": case_input.get("baseBranch"),
        },
        preflight_provider=lambda: {
            "ready": True,
            "sources": [
                {
                    "id": "github-api",
                    "name": "GitHub REST API",
                    "configured": True,
                    "reachable": None,
                    "state": "checked_on_run",
                    "authentication": "token_or_anonymous",
                }
            ],
            "runtime": "release-readiness-real-case-v1",
        },
    )
