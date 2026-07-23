# Claude Code Generic Case MCP Demo

This project consumes both the Finance and Release Readiness Case Packs through the
generic `rogueskills-case-mcp` stdio server. The Bridge does not receive SEC, GitHub,
market-data, LLM, or provider credentials.

Start RogueSkills from the repository root with the real Provider configuration:

```bash
npm start
```

Then start Claude Code from this directory:

```bash
cd examples/claude-case-demo
claude
```

Example Release Readiness request:

```text
Use the approved release-readiness Case Pack to inspect openai/openai-python main.
Run a Live Case with auto evolution disabled. Report the check counts, evidence gaps,
recommendation, Case ID, score, hard-gate status, and runtimeVerified state.
```

The `.mcp.json` allowlist intentionally contains only `finance-stock-analysis` and
`release-readiness`; adding another Pack requires an explicit project configuration change.
