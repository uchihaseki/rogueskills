"""Exercise generic MCP tools against the persisted real GitHub Source Bundle."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from rogueskills.api.app import create_app
from rogueskills.mcp.api_client import RogueSkillsApiClient
from rogueskills.mcp.case_bridge import CaseMcpBridge
from rogueskills.settings import Settings

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "release-live.db"
LIVE_CASE_ID = "case-run-c13f4265126a4e2ca3eb58b5b61b61f3"


async def call_tool(
    bridge: CaseMcpBridge,
    message_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = await bridge.server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    if response is None:
        raise RuntimeError(f"MCP tool returned no response: {name}")
    result = response["result"]
    if result["isError"]:
        raise RuntimeError(result["structuredContent"])
    return result["structuredContent"]


async def main() -> None:
    settings = Settings(
        database_url=f"sqlite:///{DATABASE}",
        project_root=Path(__file__).resolve().parents[2],
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        api = RogueSkillsApiClient(
            base_url="http://rogueskills.local",
            transport=httpx.ASGITransport(app=app),
        )
        bridge = CaseMcpBridge(
            api,
            allowed_case_pack_ids={"release-readiness"},
        )
        try:
            pack = app.state.case_pack_registry.get("release-readiness")
            gateway_calls_before = getattr(pack.data_gateway, "calls", None)
            catalog = await call_tool(bridge, 1, "list_case_packs", {})
            pack_detail = await call_tool(
                bridge,
                2,
                "get_case_pack",
                {"casePackId": "release-readiness", "casePackVersion": "1.0.0"},
            )
            run = await call_tool(
                bridge,
                3,
                "run_case",
                {
                    "casePackId": "release-readiness",
                    "casePackVersion": "1.0.0",
                    "skillId": "release-readiness-base",
                    "skillVersionId": "release-readiness-base@1",
                    "input": {
                        "repository": "openai/openai-python",
                        "ref": "main",
                        "baseBranch": None,
                        "maxPullRequests": 20,
                    },
                    "mode": "verified_replay",
                    "replayCaseId": LIVE_CASE_ID,
                    "autoEvolve": False,
                },
            )
            loaded = await call_tool(
                bridge, 4, "get_case_run", {"caseId": run["caseId"]}
            )
            report = await call_tool(
                bridge,
                5,
                "get_case_report",
                {"caseId": run["caseId"], "stage": "final", "factLimit": 3},
            )
            evaluation = await call_tool(
                bridge,
                6,
                "get_case_evaluation",
                {"caseId": run["caseId"], "stage": "final"},
            )
            gateway_calls_after = getattr(pack.data_gateway, "calls", None)
            evidence = {
                "server": {
                    "name": bridge.server.name,
                    "version": bridge.server.version,
                },
                "approvedCasePacks": [item["ref"] for item in catalog["casePacks"]],
                "inputSchemaAvailable": bool(
                    pack_detail["casePack"].get("inputSchema")
                ),
                "run": run,
                "loadedRunMatches": loaded["caseId"] == run["caseId"],
                "reportWindow": report["window"],
                "returnedFactIds": [item["id"] for item in report["report"]["facts"]],
                "evaluation": evaluation["evaluation"],
                "liveGatewayCallsBefore": gateway_calls_before,
                "liveGatewayCallsAfter": gateway_calls_after,
                "replayAvoidedLiveGateway": gateway_calls_before == gateway_calls_after == 0,
            }
            if not all(
                [
                    run["runtimeVerified"],
                    evidence["loadedRunMatches"],
                    evaluation["evaluation"]["hardGatesPassed"],
                    evidence["replayAvoidedLiveGateway"],
                ]
            ):
                raise RuntimeError("Generic MCP Replay verification failed")
            output = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
            (ROOT / "06-generic-mcp-replay.json").write_text(output, encoding="utf-8")
            print(json.dumps(evidence, ensure_ascii=False))
        finally:
            await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
