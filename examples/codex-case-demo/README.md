# Codex Generic Case MCP Demo

This clean project consumes both the Finance and Release Readiness Case Packs through
the generic `rogueskills.mcp.case_bridge` stdio server. Codex reads the project-level
`.codex/config.toml` and starts the same Bridge used by Claude Code.

Start the RogueSkills API from the repository root with the real Provider configuration:

```bash
npm start
```

Then start Codex from this directory:

```bash
cd examples/codex-case-demo
codex
```

Example request:

```text
Use the approved release-readiness Case Pack to inspect openai/openai-python main.
Run a Verified Replay for replay Case ID case-run-c13f4265126a4e2ca3eb58b5b61b61f3,
keep auto evolution disabled, and report the check counts, recommendation, Case ID,
score, hard-gate status, and runtimeVerified state.
```

Codex does not load Claude Code's `.mcp.json`; the equivalent registration for an
existing project is documented in `ROGUESKILLS-CODEX-INSTALL.md` in exported packages.
The project config intentionally allowlists only `finance-stock-analysis` and
`release-readiness` and pins their default Skill Versions.

For the non-interactive Host smoke with a persisted real GitHub Source Bundle, run:

```bash
zsh artifacts/release-e2e-20260723/run_codex_mcp_release_demo.sh
```
