# Claude Code Finance MCP Demo

This project is the local Claude Code consumer for the RogueSkills Finance MCP Bridge.

Start RogueSkills from the repository root with its real LLM/Provider configuration and the
database that contains the verified `sop-9e7795` Finance Skill:

```bash
ROGUESKILLS_DATABASE_URL="sqlite:////Users/shuo/workspace/code/rogueskills/artifacts/finance-e2e-20260722/prior-real.db" npm start
```

Then start Claude Code from this directory so it discovers `.mcp.json` and `CLAUDE.md`:

```bash
cd examples/claude-finance-demo
claude
```

Example request:

```text
Use RogueSkills to analyze AAPL as of 2026-07-21 with real public data. Keep auto evolution disabled, preserve source warnings, and report the Case ID and runtime verification state.
```

The relative Python and `PYTHONPATH` values in `.mcp.json` assume this directory remains inside the RogueSkills repository. Exported packages use the installed `rogueskills-finance-mcp` command instead.

For a non-interactive Host smoke that starts the API, invokes Claude Code, and saves a
JSON transcript, run:

```bash
zsh artifacts/finance-e2e-20260722/run_claude_mcp_aapl_demo.sh
```

This uses the already persisted real AAPL Source Bundle in Verified Replay mode; it
does not use test fixtures or MockTransport.
