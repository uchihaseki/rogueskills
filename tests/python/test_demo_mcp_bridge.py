from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from rogueskills.contracts.demo_mcp import DemoMcpPresetRequest
from rogueskills.mcp.api_client import RogueSkillsApiClient
from rogueskills.mcp.case_bridge import CaseMcpBridge


def _skill() -> dict[str, object]:
    return {
        "id": "alphaear-signal-tracker-90641e",
        "name": "alphaear-signal-tracker",
        "description": "Track public-company signals with evidence.",
        "status": "initial",
        "currentVersionId": "alphaear-signal-tracker-90641e@2",
        "sourceId": "awesome-finance-skills",
        "genome": {
            "id": "alphaear-signal-tracker-90641e",
            "name": "alphaear-signal-tracker",
            "description": "Track public-company signals with evidence.",
            "metadata": {"category": "finance"},
            "evaluation": {"score": 85.7},
            "workflow": {
                "steps": [{"id": "step-1", "order": 1, "instruction": "Collect evidence."}]
            },
            "constraints": ["Cite every claim."],
        },
    }


def _run_record() -> dict[str, object]:
    return {
        "run": {
            "id": "run-demo-1",
            "seed": "ROGUE-0714",
            "status": "victory",
            "phase": "ended",
            "baseSkillId": "alphaear-signal-tracker-90641e",
            "skillName": "alphaear-signal-tracker",
            "scenarioId": "finance",
            "mutationIds": ["source_triangulation", "risk_register"],
            "evolutionIds": ["evidence_grade_analyst"],
            "completedNodeIds": ["n1", "n2"],
            "map": [{"layers": [[{}, {}]]}],
            "automation": {"status": "completed"},
        },
        "revision": 13,
        "baseSkillVersionId": "alphaear-signal-tracker-90641e@2",
        "artifact": {
            "id": "preset-demo-1",
            "digest": "sha256:demo",
            "evaluationEvidence": {"runtimeVerified": False},
        },
    }


@pytest.mark.asyncio
async def test_codex_demo_tools_discover_latest_skill_run_and_preset() -> None:
    requests: list[str] = []
    run = _run_record()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/api/library/initial":
            return httpx.Response(200, json={"skills": [_skill()]})
        if request.url.path == "/api/skills/alphaear-signal-tracker-90641e":
            return httpx.Response(200, json={"skill": _skill()})
        if request.url.path == "/api/skill-versions/alphaear-signal-tracker-90641e@2":
            return httpx.Response(
                200,
                json={
                    "version": {
                        "id": "alphaear-signal-tracker-90641e@2",
                        "skillId": _skill()["id"],
                        "genome": _skill()["genome"],
                    }
                },
            )
        if request.url.path == "/api/runs" and request.method == "GET":
            return httpx.Response(200, json={"runs": [run]})
        if request.url.path == "/api/runs/run-demo-1":
            return httpx.Response(200, json=run)
        if request.url.path == "/api/evolution/catalog":
            return httpx.Response(
                200,
                json={
                    "mutations": [
                        {
                            "id": "source_triangulation",
                            "name": "Source Triangulation",
                            "benefit": "Cross-check sources.",
                        },
                        {"id": "risk_register", "name": "Risk Register", "benefit": "Track risks."},
                    ],
                    "evolutions": [
                        {"id": "evidence_grade_analyst", "name": "Evidence Grade Analyst"}
                    ],
                },
            )
        if request.url.path == "/api/agent-presets/preset-demo-1":
            return httpx.Response(
                200, json={"preset": {"id": "preset-demo-1", "digest": "sha256:demo"}}
            )
        if request.url.path == "/api/demo/context":
            return httpx.Response(
                200,
                json={
                    "available": True,
                    "message": "latest",
                    "skill": _skill(),
                    "run": run,
                    "artifact": run["artifact"],
                    "catalog": {"mutations": [], "evolutions": []},
                },
            )
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "not found"}})

    api = RogueSkillsApiClient(
        base_url="http://127.0.0.1:5173",
        transport=httpx.MockTransport(handler),
    )
    bridge = CaseMcpBridge(api, allowed_case_pack_ids={"finance-stock-analysis"})
    try:
        calls = [
            ("list_initial_skills", {}),
            ("get_skill", {"skillId": "alphaear-signal-tracker-90641e"}),
            ("get_skill_version", {"skillVersionId": "alphaear-signal-tracker-90641e@2"}),
            ("list_evolution_runs", {"limit": 1}),
            ("get_evolution_run", {"runId": "run-demo-1"}),
            ("get_agent_preset", {"presetId": "preset-demo-1"}),
            ("get_demo_context", {}),
        ]
        results = []
        for index, (name, arguments) in enumerate(calls, start=1):
            response = await bridge.server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            )
            assert response is not None
            results.append(response["result"])
    finally:
        await bridge.close()

    assert all(result["isError"] is False for result in results)
    assert results[0]["structuredContent"]["skills"][0]["id"] == _skill()["id"]
    assert results[3]["structuredContent"]["runs"][0]["artifactId"] == "preset-demo-1"
    assert results[4]["structuredContent"]["mutationDetails"][0]["id"] == "source_triangulation"
    assert results[6]["structuredContent"]["available"] is True
    assert "/api/demo/context" in requests


def test_preset_tool_requires_exactly_one_reference() -> None:
    with pytest.raises(ValidationError):
        DemoMcpPresetRequest.model_validate({})
    with pytest.raises(ValidationError):
        DemoMcpPresetRequest.model_validate({"presetId": "preset-1", "runId": "run-1"})
