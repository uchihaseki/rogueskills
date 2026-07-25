"""Generic Case MCP entrypoint with Finance aliases kept for compatibility."""

from __future__ import annotations

import asyncio
from typing import Any

from .api_client import RogueSkillsApiClient
from .finance_bridge import FinanceMcpBridge
from .protocol import run_stdio


class CaseMcpBridge(FinanceMcpBridge):
    def __init__(self, api: RogueSkillsApiClient, **kwargs: Any) -> None:
        super().__init__(
            api,
            server_name="rogueskills-cases",
            include_demo_tools=True,
            **kwargs,
        )


async def _run() -> None:
    bridge = CaseMcpBridge(RogueSkillsApiClient.from_environment())
    try:
        await run_stdio(bridge.server)
    finally:
        await bridge.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
