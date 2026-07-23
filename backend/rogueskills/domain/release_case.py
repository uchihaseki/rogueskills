from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from rogueskills.contracts.case_runtime import CaseEvaluation, CaseMutationProposal
from rogueskills.contracts.release_case import ReleaseReadinessReport

EVIDENCE_WORKFLOW_INSTRUCTION = (
    "Capture candidate commit, check-run, pull-request, and rollback evidence with immutable "
    "GitHub URLs and evidence IDs before declaring release readiness."
)
MISSING_CI_INSTRUCTION = (
    "When candidate CI check runs are absent, return review, record the data gap, and never "
    "infer a successful status."
)
READINESS_CONSTRAINT = (
    "Never declare a release ready when required CI evidence is missing or failing."
)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_release_dataset(
    bundle: dict[str, Any], case_input: dict[str, Any] | None = None
) -> dict[str, Any]:
    del case_input
    repository = bundle["repository"]
    commit = bundle["commit"]
    check_runs = bundle["checkRuns"].get("check_runs", [])
    pulls = bundle["openPullRequests"]
    failing = [
        item
        for item in check_runs
        if item.get("status") == "completed"
        and item.get("conclusion") not in {"success", "neutral", "skipped"}
    ]
    pending = [item for item in check_runs if item.get("status") != "completed"]
    successful = [
        item
        for item in check_runs
        if item.get("status") == "completed"
        and item.get("conclusion") in {"success", "neutral", "skipped"}
    ]
    draft_pulls = [item for item in pulls if item.get("draft") is True]
    facts = [
        {
            "id": "fact-release-commit",
            "metric": "candidate_commit",
            "value": commit["sha"],
            "unit": "sha",
            "sourceEvidenceId": "github-commit",
        },
        {
            "id": "fact-release-check-total",
            "metric": "check_total",
            "value": len(check_runs),
            "unit": "count",
            "sourceEvidenceId": "github-check-runs",
        },
        {
            "id": "fact-release-check-successful",
            "metric": "check_successful",
            "value": len(successful),
            "unit": "count",
            "sourceEvidenceId": "github-check-runs",
        },
        {
            "id": "fact-release-check-failing",
            "metric": "check_failing",
            "value": len(failing),
            "unit": "count",
            "sourceEvidenceId": "github-check-runs",
        },
        {
            "id": "fact-release-check-pending",
            "metric": "check_pending",
            "value": len(pending),
            "unit": "count",
            "sourceEvidenceId": "github-check-runs",
        },
        {
            "id": "fact-release-open-pulls",
            "metric": "open_pull_requests",
            "value": len(pulls),
            "unit": "count",
            "sourceEvidenceId": "github-open-pulls",
        },
        {
            "id": "fact-release-draft-pulls",
            "metric": "draft_pull_requests",
            "value": len(draft_pulls),
            "unit": "count",
            "sourceEvidenceId": "github-open-pulls",
        },
    ]
    pass_rate = len(successful) / len(check_runs) * 100 if check_runs else 0.0
    derived = [
        {
            "id": "metric-release-check-pass-rate",
            "label": "Completed successful check rate",
            "value": round(pass_rate, 2),
            "unit": "%",
            "formula": "successful / total × 100",
            "inputFactIds": [
                "fact-release-check-total",
                "fact-release-check-successful",
            ],
            "evidenceIds": ["github-check-runs"],
        }
    ]
    return {
        "repository": {
            "fullName": repository["full_name"],
            "defaultBranch": repository.get("default_branch"),
            "private": bool(repository.get("private", False)),
            "archived": bool(repository.get("archived", False)),
        },
        "ref": bundle["ref"],
        "baseBranch": bundle["baseBranch"],
        "commitSha": commit["sha"],
        "sources": bundle["sources"],
        "facts": facts,
        "derivedMetrics": derived,
        "checkRuns": check_runs,
        "openPullRequests": pulls,
        "warnings": bundle.get("warnings", []),
        "validEvidenceIds": {
            *[item["id"] for item in bundle["sources"]],
            *[item["id"] for item in facts],
            *[item["id"] for item in derived],
        },
    }


def _fact_values(dataset: dict[str, Any]) -> dict[str, Any]:
    return {item["metric"]: item["value"] for item in dataset["facts"]}


def expected_recommendation(dataset: dict[str, Any]) -> str:
    facts = _fact_values(dataset)
    if dataset["repository"]["archived"] or int(facts["check_failing"]) > 0:
        return "blocked"
    if (
        int(facts["check_pending"]) > 0
        or int(facts["check_total"]) == 0
        or int(facts["draft_pull_requests"]) > 0
    ):
        return "review"
    return "ready"


def build_release_report(
    *,
    case_input: dict[str, Any],
    dataset: dict[str, Any],
    evidence_workflow_enabled: bool = True,
) -> dict[str, Any]:
    facts = _fact_values(dataset)
    total = int(facts["check_total"])
    failing = int(facts["check_failing"])
    pending = int(facts["check_pending"])
    recommendation = expected_recommendation(dataset)
    findings = [
        {
            "id": "finding-candidate-commit",
            "severity": "info",
            "claim": f"Candidate ref resolves to {dataset['commitSha']}.",
            "evidenceIds": ["fact-release-commit"],
        },
        {
            "id": "finding-ci-state",
            "severity": (
                "blocking" if failing else "warning" if pending or total == 0 else "info"
            ),
            "claim": f"Checks: total={total}, failing={failing}, pending={pending}.",
            "evidenceIds": [
                "fact-release-check-total",
                "fact-release-check-failing",
                "fact-release-check-pending",
            ],
        },
        {
            "id": "finding-open-work",
            "severity": "warning" if dataset["openPullRequests"] else "info",
            "claim": (
                "Open pull requests against "
                f"{dataset['baseBranch']}: {len(dataset['openPullRequests'])}."
            ),
            "evidenceIds": ["fact-release-open-pulls", "fact-release-draft-pulls"],
        },
    ]
    if not evidence_workflow_enabled:
        findings[1]["evidenceIds"] = []
    data_gaps = [
        "The pull-request listing proves open-work state but does not prove review approval."
    ]
    if total == 0:
        data_gaps.append("No check runs were returned for the candidate commit.")
    report = ReleaseReadinessReport(
        id=f"release-report-{uuid4().hex}",
        caseId=str(case_input["caseId"]),
        stage=case_input["stage"],
        generatedAt=_iso_now(),
        skillId=str(case_input["skillId"]),
        skillVersionId=str(case_input["skillVersionId"]),
        repository={
            **dataset["repository"],
            "ref": dataset["ref"],
            "baseBranch": dataset["baseBranch"],
            "commitSha": dataset["commitSha"],
        },
        sources=dataset["sources"],
        facts=dataset["facts"],
        derivedMetrics=dataset["derivedMetrics"],
        recommendation=recommendation,
        summary=(
            f"Release readiness for {dataset['repository']['fullName']}@{dataset['ref']}: "
            f"{recommendation}."
        ),
        findings=findings,
        warnings=dataset["warnings"],
        dataGaps=data_gaps,
    )
    return report.model_dump(mode="json")


def release_evidence_workflow_enabled(genome: dict[str, Any]) -> bool:
    text = " ".join(
        [
            *[
                str(item.get("instruction") or "")
                for item in genome.get("workflow", {}).get("steps", [])
            ],
            *[str(item) for item in genome.get("constraints", [])],
        ]
    ).lower()
    return "github" in text and "check-run" in text and "evidence id" in text


def evaluate_release_report(
    report: dict[str, Any], dataset: dict[str, Any]
) -> CaseEvaluation:
    sources = report["sources"]
    source_ids = {item["id"] for item in sources}
    required_sources = {
        "github-repository",
        "github-commit",
        "github-check-runs",
        "github-open-pulls",
    }
    source_integrity = required_sources.issubset(source_ids) and all(
        str(item.get("url", "")).startswith("https://api.github.com/")
        and re.fullmatch(r"sha256:[0-9a-f]{64}", str(item.get("sha256", "")))
        and bool(item.get("revision"))
        for item in sources
    )
    valid_ids = dataset["validEvidenceIds"]
    cited = all(
        item.get("evidenceIds")
        and all(reference in valid_ids for reference in item["evidenceIds"])
        for item in report["findings"]
    )
    report_facts = {item["metric"]: item for item in report["facts"]}
    expected_facts = {item["metric"]: item for item in dataset["facts"]}
    fact_integrity = set(report_facts) == set(expected_facts) and all(
        report_facts[metric].get("value") == expected.get("value")
        and report_facts[metric].get("sourceEvidenceId")
        == expected.get("sourceEvidenceId")
        for metric, expected in expected_facts.items()
    )
    total_checks = int(expected_facts["check_total"]["value"])
    ci_evidence = total_checks > 0 and "github-check-runs" in source_ids
    review_evidence = (
        "github-open-pulls" in source_ids and "open_pull_requests" in report_facts
    )
    expected_decision = expected_recommendation(dataset)
    recommendation_consistent = report["recommendation"] == expected_decision
    cases = [
        {
            "id": "source-integrity",
            "label": "Immutable GitHub source integrity",
            "score": 100.0 if source_integrity else 0.0,
            "weight": 20,
            "passed": source_integrity,
            "hardGate": True,
            "details": f"{len(sources)} GitHub snapshots",
            "evidenceRefs": sorted(source_ids),
        },
        {
            "id": "finding-citations",
            "label": "Finding evidence references",
            "score": 100.0 if cited else 0.0,
            "weight": 20,
            "passed": cited,
            "hardGate": True,
            "details": "All findings cite captured evidence" if cited else "Missing evidence",
            "evidenceRefs": [],
        },
        {
            "id": "no-fabricated-status",
            "label": "No fabricated source or check status",
            "score": 100.0 if fact_integrity else 0.0,
            "weight": 20,
            "passed": fact_integrity,
            "hardGate": True,
            "details": "Report facts match the deterministic dataset",
            "evidenceRefs": [item["id"] for item in dataset["facts"]],
        },
        {
            "id": "ci-evidence",
            "label": "Candidate CI evidence",
            "score": 100.0 if ci_evidence else 0.0,
            "weight": 15,
            "passed": ci_evidence,
            "hardGate": True,
            "details": f"{total_checks} check run(s)",
            "evidenceRefs": ["github-check-runs"],
        },
        {
            "id": "review-evidence",
            "label": "Pull-request review-work evidence",
            "score": 100.0 if review_evidence else 0.0,
            "weight": 10,
            "passed": review_evidence,
            "hardGate": True,
            "details": "Open pull-request state captured; approval is explicitly a data gap",
            "evidenceRefs": ["github-open-pulls"],
        },
        {
            "id": "recommendation-consistency",
            "label": "Recommendation consistency",
            "score": 100.0 if recommendation_consistent else 0.0,
            "weight": 15,
            "passed": recommendation_consistent,
            "hardGate": True,
            "details": f"Expected recommendation: {expected_decision}",
            "evidenceRefs": [
                "fact-release-check-total",
                "fact-release-check-failing",
                "fact-release-check-pending",
            ],
        },
    ]
    score = sum(item["score"] * item["weight"] for item in cases) / 100
    hard_gates = all(item["passed"] for item in cases if item["hardGate"])
    passed = score >= 85 and hard_gates
    return CaseEvaluation(
        evaluationId=f"release-eval-{uuid4().hex}",
        benchmarkId="release-readiness-real-case-v1",
        algorithmVersion="release-readiness-evaluator-v1",
        runtimeVerified=passed,
        passed=passed,
        score=score,
        hardGatesPassed=hard_gates,
        cases=cases,
        failedCaseIds=[item["id"] for item in cases if not item["passed"]],
        summary="Release readiness evidence passed" if passed else "Release evidence has gaps",
    )


def plan_release_mutation(
    genome: dict[str, Any], evaluation: CaseEvaluation
) -> CaseMutationProposal:
    steps = genome.get("workflow", {}).get("steps", [])
    next_order = max((int(item.get("order", 0)) for item in steps), default=0) + 1
    patch: list[dict[str, Any]] = []
    existing_instructions = {item.get("instruction") for item in steps}
    instructions: list[str] = []
    if "finding-citations" in evaluation.failedCaseIds or "source-integrity" in evaluation.failedCaseIds:
        instructions.append(EVIDENCE_WORKFLOW_INSTRUCTION)
    if "ci-evidence" in evaluation.failedCaseIds:
        instructions.append(MISSING_CI_INSTRUCTION)
    for instruction in instructions:
        if instruction not in existing_instructions:
            patch.append(
                {
                    "op": "add",
                    "path": "/workflow/steps/-",
                    "value": {
                        "id": f"release-evidence-{next_order}",
                        "order": next_order,
                        "instruction": instruction,
                    },
                }
            )
            next_order += 1
    if READINESS_CONSTRAINT not in genome.get("constraints", []):
        patch.append({"op": "add", "path": "/constraints/-", "value": READINESS_CONSTRAINT})
    return CaseMutationProposal(
        id=f"release-mutation-{uuid4().hex}",
        sourceSkillVersionId=str(genome.get("id") or "unknown"),
        name="Release Evidence Guard",
        reason="; ".join(evaluation.failedCaseIds) or "No failed evaluator cases",
        evidenceRefs=evaluation.failedCaseIds,
        tradeoff="Adds GitHub evidence requests and validation latency.",
        tags=["release-readiness", "github-evidence"],
        genomePatch=patch,
        algorithmVersion="release-readiness-planner-v1",
    )
