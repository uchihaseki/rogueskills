# Real Finance Case Demo

This demo is the runtime half of the finance workflow. It consumes an Initial Skill
from `/api/scenarios/finance/bootstrap`, retrieves a public-company dataset from SEC
EDGAR and a dated market close from Stooq, asks the configured OpenAI-compatible
analyst to produce a structured report, evaluates evidence and arithmetic, and may
apply a real JSON Patch to the Skill Genome before rerunning the report.

The demo does not use fixture data in the live path. `verified_replay` is supported
only after a live case has persisted its real source bundle; replay keeps the original
URLs, fetch times and SHA-256 values and never relabels them as live data.

## Configuration

```sh
ROGUESKILLS_LLM_BASE_URL=http://your-model-host/v1 \
ROGUESKILLS_LLM_MODEL=your-model \
ROGUESKILLS_LLM_TIMEOUT_SECONDS=180 \
ROGUESKILLS_SEC_USER_AGENT='RogueSkills demo research-team@example.com' \
npm start
```

`ROGUESKILLS_SEC_USER_AGENT` should identify the operator and include a reachable
contact address in a deployed environment. SEC EDGAR, Stooq and the LLM must be
reachable from the backend process.

## UI path

1. Open `http://127.0.0.1:5174/discovery` and use **金融场景** to create or reuse an
   Initial Finance Skill.
2. Open `http://127.0.0.1:5174/finance-demo`.
3. Enter `AAPL`, choose an analysis date, choose the Initial Skill, and select
   **LIVE · 重新抓取**.
4. Run the case. The result shows source snapshots, SEC facts, derived metrics,
   two-method valuation sensitivity, baseline evaluation, Mutation JSON Patch, and
   the final evaluation.

## API path

```text
GET  /api/finance/cases/preflight
POST /api/finance/cases
GET  /api/finance/cases/{caseId}
GET  /api/finance/cases/{caseId}/report?stage=baseline|evolved|final
GET  /api/finance/cases/{caseId}/agent-preset
```

Example request:

```json
{
  "ticker": "AAPL",
  "skillId": "<initial-finance-skill-id>",
  "asOfDate": "2026-07-21",
  "mode": "live",
  "autoEvolve": true
}
```

The run is accepted as runtime-verified only when source integrity, fact-level
citations, period/unit completeness, derived-metric reconciliation, valuation
sensitivity, and the investment-advice boundary all pass. A Mutation is persisted as
a new Skill Version only when the evolved score is strictly higher and all hard gates
pass. The generated runtime evidence is stored in that Skill Version as
`runtimeVerification.runtimeVerified=true`.

When the final evaluation passes, the same Case also creates a candidate AgentPreset
whose `evaluationEvidence.mode` is `real-finance-case-v1` and whose runtime config
loads with `runtimeVerified=true`. It is available from
`GET /api/finance/cases/{caseId}/agent-preset` and can be exported through the normal
`/api/agent-presets/{presetId}/export/universal` endpoint.

## Test path

```sh
ROGUESKILLS_GITHUB_TOKEN= \
PYTHONPATH=backend .venv/bin/python -m pytest tests/python -q
npm run type-check --prefix frontend
npm run build --prefix frontend
```

The test suite uses isolated transport fixtures only for unit and API tests. Those
fixtures are not reachable from the live UI or the production finance case service.
