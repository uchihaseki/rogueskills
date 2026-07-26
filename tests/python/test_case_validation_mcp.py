from __future__ import annotations

from copy import deepcopy

import httpx
import pytest

from rogueskills.contracts.case_validation_mcp import CaseValidationMcpEmptyInput
from rogueskills.mcp.api_client import RogueSkillsApiClient
from rogueskills.mcp.case_bridge import CaseMcpBridge


def _validation(status: str = "succeeded") -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "id": "case-validation-demo-001",
        "idempotencyKey": "sha256:" + "a" * 64,
        "sourceRunId": "run-demo-001",
        "candidatePresetId": "preset-demo-001",
        "candidatePresetDigest": "sha256:" + "b" * 64,
        "casePackId": "finance-stock-analysis",
        "casePackVersion": "1.0.0",
        "mode": "verified_replay",
        "replayCaseId": "finance-case-demo-001",
        "input": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
        "skillId": "alphaear-signal-tracker-90641e",
        "baseSkillVersionId": "alphaear-signal-tracker-90641e@2",
        "status": status,
        "phase": "completed" if status == "succeeded" else "executing_candidate",
        "sourceBundleDigest": "sha256:" + "c" * 64,
        "datasetDigest": "sha256:" + "d" * 64,
        "executionPolicyDigest": "sha256:" + "e" * 64,
        "candidate": {
            "report": {
                "company": {"ticker": "AAPL", "name": "Apple Inc."},
                "asOfDate": "2026-07-21",
                "sources": [{"id": "sec-companyfacts"}],
                "narrative": {
                    "summary": "Evidence-bound AAPL conclusion.",
                    "findings": [{"id": "finding-1", "claim": "Revenue remained material."}],
                    "risks": [{"id": "risk-1", "risk": "Demand may weaken."}],
                    "dataGaps": [],
                    "conclusionBoundary": "Public-information research only.",
                },
            }
        },
        "comparison": {
            "baselineScore": 88.0,
            "candidateScore": 100.0,
            "scoreDelta": 12.0,
            "baselinePassed": False,
            "candidatePassed": True,
            "baselineHardGatesPassed": False,
            "candidateHardGatesPassed": True,
            "baselineFailedCaseIds": ["claim-citations"],
            "candidateFailedCaseIds": [],
            "repairedCaseIds": ["claim-citations"],
            "regressedCaseIds": [],
            "runtimeVerified": True,
            "accepted": True,
        },
        "contributionCoverage": [
            {
                "kind": "mutation",
                "id": "source_triangulation",
                "targetCaseIds": ["claim-citations"],
                "repairedCaseIds": ["claim-citations"],
                "attribution": "associated_not_causal",
            }
        ],
        "runtimeVerified": True,
        "accepted": True,
        "promotion": {
            "status": "created",
            "promoted": True,
            "evolvedSkillVersionId": "alphaear-signal-tracker-90641e@3",
            "currentSkillVersionId": "alphaear-signal-tracker-90641e@3",
            "error": None,
        },
        "createdAt": "2026-07-25T00:00:00Z",
        "completedAt": "2026-07-25T00:00:01Z",
        "revision": 12,
        "error": None,
    }


@pytest.mark.asyncio
async def test_case_validation_mcp_discovers_runs_and_preserves_replay_boundary() -> None:
    state = _validation()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/runs":
            return httpx.Response(200, json={"runs": [{"run": {"id": "run-demo-001"}}]})
        if (
            request.method == "POST"
            and request.url.path == "/api/runs/run-demo-001/case-validations"
        ):
            return httpx.Response(202, json={"validation": state, "created": True})
        if request.url.path == "/api/runs/run-demo-001/case-validations":
            return httpx.Response(200, json={"validations": [state]})
        if request.url.path == "/api/runs/run-demo-001":
            return httpx.Response(
                200,
                json={
                    "run": {
                        "id": "run-demo-001",
                        "mutationIds": ["source_triangulation"],
                        "evolutionIds": ["evidence_grade_analyst"],
                        "nodeHistory": [
                            {
                                "nodeId": "a1-l1-n1",
                                "sequence": 1,
                                "status": "completed",
                                "regionName": "证据完整性",
                                "type": "normal",
                                "reward": {
                                    "selectedMutationId": "source_triangulation",
                                    "unlockedEvolutionIds": ["evidence_grade_analyst"],
                                },
                            }
                        ],
                    }
                },
            )
        if request.url.path == "/api/evolution/catalog":
            return httpx.Response(
                200,
                json={
                    "mutations": [{"id": "source_triangulation", "name": "来源交叉验证"}],
                    "evolutions": [{"id": "evidence_grade_analyst", "name": "证据级分析"}],
                },
            )
        if request.url.path == "/api/case-validations/case-validation-demo-001":
            return httpx.Response(200, json={"validation": state})
        raise AssertionError(f"Unexpected HTTP call: {request.method} {request.url}")

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = CaseMcpBridge(api)
    try:
        latest = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_latest_case_validation_context", "arguments": {}},
            }
        )
        comparison = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_case_validation_comparison",
                    "arguments": {"validationId": state["id"]},
                },
            }
        )
        created = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "validate_evolution_run_on_case",
                    "arguments": {
                        "runId": "run-demo-001",
                        "replayCaseId": "finance-case-demo-001",
                        "input": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
                    },
                },
            }
        )
        script = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_case_validation_demo_script", "arguments": {}},
            }
        )
    finally:
        await bridge.close()

    assert latest is not None and latest["result"]["isError"] is False
    assert latest["result"]["structuredContent"]["validation"]["mode"] == "verified_replay"
    assert comparison is not None and comparison["result"]["isError"] is False
    assert comparison["result"]["structuredContent"]["comparison"]["scoreDelta"] == 12.0
    assert created is not None and created["result"]["isError"] is False
    assert created["result"]["structuredContent"]["promotionStatus"] == "created"
    assert latest["result"]["structuredContent"]["validation"]["executionPolicyDigest"] == (
        "sha256:" + "e" * 64
    )
    assert script is not None and script["result"]["isError"] is False
    script_content = script["result"]["structuredContent"]
    assert script_content["evidenceMode"] == "verified_replay"
    assert script_content["businessReport"]["company"]["ticker"] == "AAPL"
    assert script_content["candidateFormation"][0]["selectedMutationName"] == "来源交叉验证"
    assert script_content["associatedRepairs"][0]["attribution"] == "associated_not_causal"
    assert len(script_content["talkTrack"]) == 5


@pytest.mark.asyncio
async def test_latest_validation_is_sorted_by_validation_created_at_across_runs() -> None:
    older = deepcopy(_validation())
    older.update(
        {
            "id": "case-validation-older",
            "sourceRunId": "run-recently-updated",
            "createdAt": "2026-07-25T00:00:00Z",
        }
    )
    newer = deepcopy(_validation())
    newer.update(
        {
            "id": "case-validation-newer",
            "sourceRunId": "run-older-update",
            "createdAt": "2026-07-25T00:05:00Z",
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/runs":
            return httpx.Response(
                200,
                json={
                    "runs": [
                        {"run": {"id": "run-recently-updated"}},
                        {"run": {"id": "run-older-update"}},
                    ]
                },
            )
        if request.url.path == "/api/runs/run-recently-updated/case-validations":
            return httpx.Response(200, json={"validations": [older]})
        if request.url.path == "/api/runs/run-older-update/case-validations":
            return httpx.Response(200, json={"validations": [newer]})
        raise AssertionError(f"Unexpected HTTP call: {request.method} {request.url}")

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    try:
        latest = await api.get_latest_case_validation_context(CaseValidationMcpEmptyInput())
    finally:
        await api.close()

    assert latest.available is True
    assert latest.validation is not None
    assert latest.validation.validationId == "case-validation-newer"
