# Release Readiness Real Case Evidence

This directory contains the host runner and persisted evidence for the second real
Case Pack. The live path calls the fixed GitHub REST endpoints through
`GithubReleaseReadinessGateway`; it does not install a fixture or `MockTransport`.

Run from the repository root:

```sh
PYTHONPATH=backend .venv/bin/python \
  artifacts/release-e2e-20260723/run_live_release_case.py
```

Optional inputs:

```sh
ROGUESKILLS_RELEASE_REPOSITORY=owner/repository \
ROGUESKILLS_RELEASE_REF=main \
ROGUESKILLS_RELEASE_BASE_BRANCH=main \
PYTHONPATH=backend .venv/bin/python \
  artifacts/release-e2e-20260723/run_live_release_case.py
```

The runner creates one Live Case through `/api/case-runs`, verifies all hard gates,
then creates a Verified Replay from the persisted Source Bundle. It records the live
gateway call count before and after replay so replay cannot silently access GitHub.

Generated evidence:

- `00-live-preflight.json`
- `01-live-release-case.json`
- `02-live-release-summary.json`
- `03-verified-replay-case.json`
- `04-verified-replay-summary.json`
- `05-g6-gate-report.md`
- `06-generic-mcp-replay.json`
- `release-live.db`

`99-live-release-failure.json` is written if the provider, Contract, hard gates, or
Replay verification fails.

The generic MCP replay evidence in `06-generic-mcp-replay.json` exercises the same
persisted Live Source Bundle through `list_case_packs`, `get_case_pack`, `run_case`,
`get_case_run`, `get_case_report`, and `get_case_evaluation` with the Release Pack
allowlisted and no external Gateway calls.

The Codex Host demo starts the API on port 5173, verifies that Codex loaded the
project-level MCP configuration, asks `codex exec` to call the generic tools, and
validates its structured result against the persisted real GitHub Source Bundle:

```sh
zsh artifacts/release-e2e-20260723/run_codex_mcp_release_demo.sh
```

A successful Host run writes `07-codex-mcp-api.log`, `08-codex-mcp-config.json`,
`09-codex-mcp-release-events.jsonl`, and `10-codex-mcp-release-result.json`.

The `codex exec` step keeps the user's model-provider configuration (including a local
Responses proxy, when configured), but disables `apps`, `plugins`, and `remote_plugin`
for this run. The project config also disables `node_repl`, so unrelated personal or
remote MCP servers cannot interfere with this deterministic Host test.

The project explicitly allowlists the seven generic Case tools and sets
`default_tools_approval_mode = "approve"` only for `rogueskills-cases`. This avoids
non-interactive MCP confirmation cancellation without granting blanket shell approval.

The Codex run uses Verified Replay and therefore performs no new GitHub request. It
is not a mock: the Source Bundle and evaluations were captured by the Live Case above.
