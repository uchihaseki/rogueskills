from __future__ import annotations

import io
import json

import httpx
import pytest

from rogueskills.mcp.api_client import (
    RogueSkillsApiClient,
    RogueSkillsApiError,
    normalize_api_base_url,
)
from rogueskills.mcp.finance_bridge import FinanceMcpBridge
from rogueskills.mcp.protocol import serve_stdio


def _preflight_payload() -> dict[str, object]:
    return {
        "ready": True,
        "runtime": "real-finance-case-v1",
        "analyst": {
            "mode": "llm",
            "provider": "OpenAI-compatible",
            "model": "qwen-test",
            "configured": True,
        },
        "sources": [
            {
                "id": "sec-edgar",
                "name": "SEC EDGAR",
                "configured": True,
                "reachable": None,
                "state": "checked_on_run",
            }
        ],
    }


def _case_payload() -> dict[str, object]:
    evaluation = {
        "evaluationId": "finance-eval-test",
        "benchmarkId": "finance-real-case-v1",
        "algorithmVersion": "finance-evidence-evaluator-v1",
        "runtimeVerified": True,
        "passed": True,
        "score": 100.0,
        "hardGatesPassed": True,
        "cases": [
            {
                "id": "source-integrity",
                "label": "Source integrity",
                "score": 100.0,
                "weight": 1,
                "passed": True,
                "hardGate": True,
                "details": "captured",
                "evidenceRefs": ["sec-companyfacts"],
            }
        ],
        "failedCaseIds": [],
        "summary": "passed",
    }
    report = {
        "id": "report-test",
        "caseId": "finance-case-test",
        "stage": "baseline",
        "skillId": "sop-test",
        "skillVersionId": "sop-test@2",
        "sources": [
            {
                "id": "sec-companyfacts",
                "provider": "SEC EDGAR",
                "url": "https://data.sec.gov/companyfacts.json",
                "fetchedAt": "2026-07-23T00:00:00Z",
                "sha256": "sha256:" + "a" * 64,
            }
        ],
        "facts": [{"id": "fact-1"}],
        "warnings": [],
    }
    return {
        "id": "finance-case-test",
        "ticker": "AAPL",
        "asOfDate": "2026-07-21",
        "mode": "live",
        "skillId": "sop-test",
        "baseSkillVersionId": "sop-test@2",
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
        "agentPreset": {
            "id": "preset-test",
            "digest": "sha256:" + "b" * 64,
            "status": "candidate",
            "primarySkill": {"skillVersionId": "sop-test@2"},
            "evaluationEvidence": {"runtimeVerified": True},
        },
        "error": None,
    }


def test_api_base_url_rejects_embedded_credentials_and_non_http_schemes() -> None:
    assert normalize_api_base_url("http://127.0.0.1:5173/") == "http://127.0.0.1:5173"

    with pytest.raises(ValueError, match="HTTP"):
        normalize_api_base_url("file:///tmp/rogueskills.sock")
    with pytest.raises(ValueError, match="credentials"):
        normalize_api_base_url("https://user:secret@example.com")


@pytest.mark.asyncio
async def test_api_client_loads_real_preflight_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:5173/api/finance/cases/preflight"
        assert request.headers["X-Request-ID"].startswith("mcp-")
        return httpx.Response(200, json=_preflight_payload())

    client = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    try:
        preflight = await client.finance_preflight()
    finally:
        await client.close()

    assert preflight.ready is True
    assert preflight.runtime == "real-finance-case-v1"
    assert preflight.analyst.model == "qwen-test"


@pytest.mark.asyncio
async def test_api_client_preserves_upstream_error_and_request_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": {
                    "code": "FINANCE_ANALYST_NOT_CONFIGURED",
                    "message": "Analyst is unavailable.",
                    "retryable": False,
                    "details": {},
                },
                "requestId": "req-body",
            },
            headers={"X-Request-ID": "req-header"},
        )

    client = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(RogueSkillsApiError) as captured:
            await client.finance_preflight()
    finally:
        await client.close()

    assert captured.value.error.code == "FINANCE_ANALYST_NOT_CONFIGURED"
    assert captured.value.error.requestId == "req-header"
    assert captured.value.error.details["statusCode"] == 503


@pytest.mark.asyncio
async def test_api_client_classifies_timeout_and_keeps_request_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow upstream", request=request)

    client = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(RogueSkillsApiError) as captured:
            await client.finance_preflight()
    finally:
        await client.close()

    assert captured.value.error.code == "ROGUESKILLS_API_TIMEOUT"
    assert captured.value.error.retryable is True
    assert captured.value.error.requestId is not None
    assert captured.value.error.details["timeoutMs"] == 10_000


@pytest.mark.asyncio
async def test_bridge_initializes_lists_and_calls_preflight_tool() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_preflight_payload())

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(api, default_finance_skill_id="sop-test")
    try:
        initialized = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            }
        )
        tools = await bridge.server.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        called = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "finance_preflight", "arguments": {}},
            }
        )
    finally:
        await bridge.close()

    assert initialized is not None
    assert initialized["result"]["protocolVersion"] == "2024-11-05"
    assert initialized["result"]["serverInfo"]["name"] == "rogueskills-finance"
    assert tools is not None
    assert [item["name"] for item in tools["result"]["tools"]] == [
        "list_case_packs",
        "get_case_pack",
        "case_preflight",
        "run_case",
        "get_case_run",
        "get_case_report",
        "get_case_evaluation",
        "finance_preflight",
        "analyze_stock",
        "get_finance_case",
        "get_finance_report",
        "get_verified_agent_preset",
    ]
    assert tools["result"]["tools"][0]["inputSchema"]["additionalProperties"] is False
    assert tools["result"]["tools"][0]["annotations"] == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    run_case_tool = next(
        item for item in tools["result"]["tools"] if item["name"] == "run_case"
    )
    assert run_case_tool["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    }
    assert called is not None
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["ready"] is True


@pytest.mark.asyncio
async def test_bridge_core_finance_tools_use_the_api_contracts() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/finance/cases":
            body = json.loads(request.content)
            assert body == {
                "ticker": "AAPL",
                "asOfDate": "2026-07-21",
                "skillId": "sop-test",
                "mode": "live",
                "autoEvolve": False,
            }
            return httpx.Response(201, json={"case": _case_payload()})
        if request.url.path.endswith("/agent-preset"):
            return httpx.Response(200, json={"preset": _case_payload()["agentPreset"]})
        if request.url.path == "/api/finance/cases/finance-case-test":
            return httpx.Response(200, json={"case": _case_payload()})
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(api, default_finance_skill_id="sop-test")
    tool_calls = [
        (
            "analyze_stock",
            {
                "ticker": "aapl",
                "asOfDate": "2026-07-21",
            },
        ),
        ("get_finance_case", {"caseId": "finance-case-test"}),
        ("get_finance_report", {"caseId": "finance-case-test", "stage": "final"}),
        ("get_verified_agent_preset", {"caseId": "finance-case-test"}),
    ]
    results = []
    try:
        for message_id, (name, arguments) in enumerate(tool_calls, start=1):
            result = await bridge.server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            )
            assert result is not None
            results.append(result["result"])
    finally:
        await bridge.close()

    assert all(result["isError"] is False for result in results)
    assert results[0]["structuredContent"]["caseId"] == "finance-case-test"
    assert results[0]["structuredContent"]["runtimeVerified"] is True
    assert results[2]["structuredContent"]["evaluation"]["hardGatesPassed"] is True
    assert results[3]["structuredContent"]["digest"].startswith("sha256:")
    assert requests == [
        ("POST", "/api/finance/cases"),
        ("GET", "/api/finance/cases/finance-case-test"),
        ("GET", "/api/finance/cases/finance-case-test"),
        ("GET", "/api/finance/cases/finance-case-test/agent-preset"),
    ]


@pytest.mark.asyncio
async def test_bridge_returns_tool_error_for_undeclared_arguments() -> None:
    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    bridge = FinanceMcpBridge(api)
    try:
        result = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "finance_preflight",
                    "arguments": {"url": "https://unapproved.example.com"},
                },
            }
        )
    finally:
        await bridge.close()

    assert result is not None
    assert result["result"]["isError"] is True
    assert result["result"]["structuredContent"]["code"] == "INVALID_TOOL_ARGUMENTS"


@pytest.mark.asyncio
async def test_analyze_stock_requires_explicit_or_configured_finance_skill() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not run without an approved Finance Skill")

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(api, default_finance_skill_id=None)
    try:
        result = await bridge.server.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "analyze_stock",
                    "arguments": {"ticker": "AAPL", "asOfDate": "2026-07-21"},
                },
            }
        )
    finally:
        await bridge.close()

    assert result is not None
    assert result["result"]["isError"] is True
    assert result["result"]["structuredContent"]["code"] == "FINANCE_SKILL_ID_REQUIRED"


@pytest.mark.asyncio
async def test_stdio_transport_uses_newline_delimited_json_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_preflight_payload())

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = FinanceMcpBridge(api)
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "finance_preflight", "arguments": {}},
        },
    ]
    reader = io.StringIO("".join(json.dumps(item) + "\n" for item in messages))
    writer = io.StringIO()
    try:
        await serve_stdio(bridge.server, reader=reader, writer=writer)
    finally:
        await bridge.close()

    responses = [json.loads(line) for line in writer.getvalue().splitlines()]
    assert [item["id"] for item in responses] == [1, 2, 3]
    assert responses[-1]["result"]["structuredContent"]["ready"] is True
