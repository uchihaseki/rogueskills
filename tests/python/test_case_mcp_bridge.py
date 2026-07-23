from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from rogueskills.contracts.case_mcp import CaseMcpRunInput, summarize_case_run
from rogueskills.mcp.api_client import RogueSkillsApiClient
from rogueskills.mcp.case_bridge import CaseMcpBridge
from rogueskills.mcp.finance_bridge import FinanceMcpBridge


def _evaluation() -> dict[str, object]:
    return {
        "evaluationId": "release-eval-test",
        "benchmarkId": "release-readiness-real-case-v1",
        "algorithmVersion": "release-readiness-evaluator-v1",
        "runtimeVerified": True,
        "passed": True,
        "score": 100.0,
        "hardGatesPassed": True,
        "cases": [
            {
                "id": "source-integrity",
                "label": "Source integrity",
                "score": 100.0,
                "weight": 100,
                "passed": True,
                "hardGate": True,
                "details": "captured",
                "evidenceRefs": ["github-check-runs"],
            }
        ],
        "failedCaseIds": [],
        "summary": "passed",
    }


def _release_case() -> dict[str, object]:
    evaluation = _evaluation()
    report = {
        "schemaVersion": "1.0.0",
        "id": "release-report-test",
        "caseId": "case-run-release-test",
        "stage": "baseline",
        "generatedAt": "2026-07-23T00:00:00Z",
        "skillId": "release-readiness-base",
        "skillVersionId": "release-readiness-base@1",
        "repository": {
            "fullName": "openai/openai-python",
            "commitSha": "a" * 40,
        },
        "sources": [
            {
                "id": "github-check-runs",
                "provider": "GitHub",
                "url": "https://api.github.com/repos/openai/openai-python/commits/main/check-runs",
                "fetchedAt": "2026-07-23T00:00:00Z",
                "revision": "a" * 40,
                "sha256": "sha256:" + "b" * 64,
            }
        ],
        "facts": [
            {
                "id": f"fact-{index}",
                "metric": f"metric-{index}",
                "value": index,
                "sourceEvidenceId": "github-check-runs",
            }
            for index in range(5)
        ],
        "derivedMetrics": [],
        "recommendation": "blocked",
        "summary": "One real check failed.",
        "findings": [],
        "warnings": [],
        "dataGaps": [],
    }
    return {
        "schemaVersion": "1.0.0",
        "id": "case-run-release-test",
        "casePackId": "release-readiness",
        "casePackVersion": "1.0.0",
        "input": {"repository": "openai/openai-python", "ref": "main"},
        "mode": "live",
        "replayCaseId": None,
        "skillId": "release-readiness-base",
        "baseSkillVersionId": "release-readiness-base@1",
        "evolvedSkillVersionId": None,
        "status": "succeeded",
        "phase": "completed",
        "runtimeVerified": True,
        "baseline": {"report": report, "evaluation": evaluation},
        "evolved": None,
        "comparison": None,
        "mutation": None,
        "finalReport": report,
        "finalEvaluation": evaluation,
        "runtimeArtifact": {
            "id": "artifact-release-test",
            "caseRunId": "case-run-release-test",
            "casePackId": "release-readiness",
            "casePackVersion": "1.0.0",
            "skillVersionId": "release-readiness-base@1",
            "evaluationId": "release-eval-test",
            "digest": "sha256:" + "c" * 64,
            "status": "candidate",
        },
        "error": None,
    }


def _case_packs() -> list[dict[str, object]]:
    return [
        {
            "id": "finance-stock-analysis",
            "version": "1.0.0",
            "ref": "finance-stock-analysis@1.0.0",
            "name": "Finance",
            "description": "Finance Case Pack",
            "capabilities": ["live"],
        },
        {
            "id": "release-readiness",
            "version": "1.0.0",
            "ref": "release-readiness@1.0.0",
            "name": "Release",
            "description": "Release Case Pack",
            "capabilities": ["live", "verified_replay"],
        },
        {
            "id": "unapproved-case",
            "version": "1.0.0",
            "ref": "unapproved-case@1.0.0",
            "name": "Unapproved",
            "description": "Must not be visible",
            "capabilities": ["live"],
        },
    ]


def test_generic_case_mcp_input_rejects_replay_mismatch_secrets_and_large_payload() -> None:
    with pytest.raises(ValidationError, match="replayCaseId"):
        CaseMcpRunInput.model_validate(
            {
                "casePackId": "release-readiness",
                "skillId": "release-readiness-base",
                "input": {"repository": "openai/openai-python"},
                "mode": "verified_replay",
            }
        )
    with pytest.raises(ValidationError, match="credentials"):
        CaseMcpRunInput.model_validate(
            {
                "casePackId": "release-readiness",
                "skillId": "release-readiness-base",
                "input": {"repository": "openai/openai-python", "token": "secret"},
            }
        )
    with pytest.raises(ValidationError, match="64 KB"):
        CaseMcpRunInput.model_validate(
            {
                "casePackId": "release-readiness",
                "skillId": "release-readiness-base",
                "input": {"content": "x" * 64_001},
            }
        )


@pytest.mark.asyncio
async def test_generic_bridge_lists_only_approved_packs_and_calls_all_case_tools() -> None:
    requests: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, str(request.url.query)))
        if request.url.path == "/api/case-packs":
            return httpx.Response(200, json={"casePacks": _case_packs()})
        if request.url.path == "/api/case-packs/release-readiness":
            assert request.url.params["version"] == "1.0.0"
            return httpx.Response(
                200,
                json={
                    "casePack": {
                        **_case_packs()[1],
                        "inputSchema": {"type": "object"},
                        "runtimePolicy": {"maxMutationAttempts": 1},
                        "skillPolicy": {"requiredCategory": "release"},
                    }
                },
            )
        if request.url.path == "/api/case-runs/preflight":
            assert request.url.params["casePackId"] == "release-readiness"
            assert request.url.params.get("casePackVersion") is None
            return httpx.Response(
                200,
                json={
                    "casePackId": "release-readiness",
                    "casePackVersion": "1.0.0",
                    "ready": True,
                    "runtime": "release-readiness-real-case-v1",
                    "sources": [{"id": "github-api", "configured": True}],
                },
            )
        if request.method == "POST" and request.url.path == "/api/case-runs":
            body = json.loads(request.content)
            assert body == {
                "casePackId": "release-readiness",
                "casePackVersion": "1.0.0",
                "skillId": "release-readiness-base",
                "skillVersionId": "release-readiness-base@1",
                "input": {"repository": "openai/openai-python", "ref": "main"},
                "mode": "live",
                "autoEvolve": False,
            }
            return httpx.Response(201, json={"caseRun": _release_case()})
        if request.url.path == "/api/case-runs/case-run-release-test":
            return httpx.Response(200, json={"caseRun": _release_case()})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = CaseMcpBridge(api, allowed_case_pack_ids={"release-readiness"})
    calls = [
        ("list_case_packs", {}),
        (
            "get_case_pack",
            {"casePackId": "release-readiness", "casePackVersion": "1.0.0"},
        ),
        ("case_preflight", {"casePackId": "release-readiness"}),
        (
            "run_case",
            {
                "casePackId": "release-readiness",
                "casePackVersion": "1.0.0",
                "skillId": "release-readiness-base",
                "skillVersionId": "release-readiness-base@1",
                "input": {"repository": "openai/openai-python", "ref": "main"},
            },
        ),
        ("get_case_run", {"caseId": "case-run-release-test"}),
        (
            "get_case_report",
            {"caseId": "case-run-release-test", "stage": "final", "factLimit": 2},
        ),
        (
            "get_case_evaluation",
            {"caseId": "case-run-release-test", "stage": "final"},
        ),
    ]
    results = []
    try:
        initialized = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            }
        )
        for message_id, (name, arguments) in enumerate(calls, start=1):
            response = await bridge.server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            )
            assert response is not None
            results.append(response["result"])
    finally:
        await bridge.close()

    assert initialized is not None
    assert initialized["result"]["serverInfo"]["name"] == "rogueskills-cases"
    assert all(result["isError"] is False for result in results)
    assert [item["id"] for item in results[0]["structuredContent"]["casePacks"]] == [
        "release-readiness"
    ]
    assert results[2]["structuredContent"]["ready"] is True
    run = results[3]["structuredContent"]
    assert run["casePackId"] == "release-readiness"
    assert run["outcome"] == "blocked"
    assert run["runtimeVerified"] is True
    assert run["artifact"]["digest"] == "sha256:" + "c" * 64
    report = results[5]["structuredContent"]
    assert report["window"]["returnedFactCount"] == 2
    assert report["window"]["hasMoreFacts"] is True
    assert report["sources"][0]["revision"] == "a" * 40
    assert results[6]["structuredContent"]["evaluation"]["hardGatesPassed"] is True
    assert any(method == "POST" and path == "/api/case-runs" for method, path, _ in requests)


@pytest.mark.asyncio
async def test_generic_bridge_denies_unapproved_pack_before_execution_and_case_details() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request.url.path == "/api/case-runs/case-run-release-test":
            return httpx.Response(200, json={"caseRun": _release_case()})
        raise AssertionError(f"Unexpected HTTP call: {request.url}")

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(api, allowed_case_pack_ids={"finance-stock-analysis"})
    try:
        denied_run = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "run_case",
                    "arguments": {
                        "casePackId": "release-readiness",
                        "skillId": "release-readiness-base",
                        "input": {"repository": "openai/openai-python"},
                    },
                },
            }
        )
        denied_read = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_case_run",
                    "arguments": {"caseId": "case-run-release-test"},
                },
            }
        )
    finally:
        await bridge.close()

    assert denied_run is not None
    assert denied_run["result"]["isError"] is True
    assert denied_run["result"]["structuredContent"]["code"] == "CASE_PACK_NOT_APPROVED"
    assert denied_read is not None
    assert denied_read["result"]["isError"] is True
    assert denied_read["result"]["structuredContent"]["code"] == "CASE_PACK_NOT_APPROVED"
    assert request_count == 1


@pytest.mark.asyncio
async def test_finance_aliases_are_denied_when_finance_pack_is_not_approved() -> None:
    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError(str(request.url)))
        ),
    )
    bridge = FinanceMcpBridge(api, allowed_case_pack_ids={"release-readiness"})
    try:
        response = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "finance_preflight", "arguments": {}},
            }
        )
    finally:
        await bridge.close()

    assert response is not None
    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["code"] == "CASE_PACK_NOT_APPROVED"


@pytest.mark.asyncio
async def test_generic_run_case_supports_finance_pack_and_verified_replay() -> None:
    submitted: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/case-runs"
        body = json.loads(request.content)
        submitted.append(body)
        case = _release_case()
        case["casePackId"] = body["casePackId"]
        case["mode"] = body["mode"]
        case["replayCaseId"] = body.get("replayCaseId")
        return httpx.Response(201, json={"caseRun": case})

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(
        api,
        allowed_case_pack_ids={"finance-stock-analysis", "release-readiness"},
        default_case_skill_versions={
            "finance-stock-analysis": "sop-finance@2",
            "release-readiness": "release-readiness-base@1",
        },
    )
    calls = [
        {
            "casePackId": "finance-stock-analysis",
            "casePackVersion": "1.0.0",
            "skillId": "sop-finance",
            "input": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
            "mode": "live",
        },
        {
            "casePackId": "release-readiness",
            "casePackVersion": "1.0.0",
            "skillId": "release-readiness-base",
            "input": {"repository": "openai/openai-python", "ref": "main"},
            "mode": "verified_replay",
            "replayCaseId": "case-run-release-live",
        },
    ]
    results = []
    try:
        for message_id, arguments in enumerate(calls, start=1):
            response = await bridge.server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "method": "tools/call",
                    "params": {"name": "run_case", "arguments": arguments},
                }
            )
            assert response is not None
            results.append(response["result"])
    finally:
        await bridge.close()

    assert all(item["isError"] is False for item in results)
    assert results[0]["structuredContent"]["casePackId"] == "finance-stock-analysis"
    assert results[1]["structuredContent"]["mode"] == "verified_replay"
    assert submitted[0]["skillVersionId"] == "sop-finance@2"
    assert submitted[1]["replayCaseId"] == "case-run-release-live"
    assert submitted[0]["autoEvolve"] is False


def test_generic_case_summary_fails_closed_and_redacts_error_details() -> None:
    case = _release_case()
    case["runtimeVerified"] = True
    case["finalEvaluation"] = {
        **_evaluation(),
        "runtimeVerified": False,
        "passed": False,
        "hardGatesPassed": False,
        "failedCaseIds": ["source-integrity"],
    }
    case["error"] = {
        "code": "PROVIDER_FAILED",
        "message": "Provider failed.",
        "retryable": True,
        "details": {"token": "secret", "nested": {"authorization": "Bearer secret"}},
    }

    summary = summarize_case_run(case)

    assert summary.runtimeVerified is False
    assert summary.error is not None
    assert summary.error.details == {
        "token": "[REDACTED]",
        "nested": {"authorization": "[REDACTED]"},
    }
