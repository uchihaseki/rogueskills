#!/bin/zsh
set -euo pipefail

ROOT="/Users/shuo/workspace/code/rogueskills"
DEMO="$ROOT/examples/codex-case-demo"
ARTIFACTS="$ROOT/artifacts/release-e2e-20260723"
DATABASE="$ARTIFACTS/release-live.db"
API_LOG="$ARTIFACTS/07-codex-mcp-api.log"
MCP_CONFIG="$ARTIFACTS/08-codex-mcp-config.json"
CODEX_EVENTS="$ARTIFACTS/09-codex-mcp-release-events.jsonl"
CODEX_RESULT="$ARTIFACTS/10-codex-mcp-release-result.json"
RESULT_SCHEMA="$ARTIFACTS/codex-release-result.schema.json"
REPLAY_CASE_ID="case-run-c13f4265126a4e2ca3eb58b5b61b61f3"

if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 5173 is already in use; stop the existing process before running this demo." >&2
  exit 1
fi

cd "$ROOT"
ROGUESKILLS_DATABASE_URL="sqlite:///$DATABASE" npm start >"$API_LOG" 2>&1 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

for _attempt in {1..60}; do
  if curl --fail --silent "http://127.0.0.1:5173/api/health" >/dev/null; then
    break
  fi
  sleep 0.5
done
curl --fail --silent "http://127.0.0.1:5173/api/health" >/dev/null

cd "$DEMO"
codex mcp get rogueskills-cases --json >"$MCP_CONFIG"

codex exec \
  --ephemeral \
  --json \
  --color never \
  --disable apps \
  --disable plugins \
  --disable remote_plugin \
  --sandbox read-only \
  --output-schema "$RESULT_SCHEMA" \
  --output-last-message "$CODEX_RESULT" \
  "Use only the rogueskills-cases MCP tools; do not use shell commands, direct HTTP, web search, or invented data. First call list_case_packs, then get_case_pack and case_preflight for release-readiness@1.0.0. Call run_case in verified_replay mode with replayCaseId $REPLAY_CASE_ID, skillId release-readiness-base, skillVersionId release-readiness-base@1, autoEvolve false, and input repository openai/openai-python, ref main, baseBranch null, maxPullRequests 20. Then call get_case_run, get_case_report with stage final and factLimit 100, and get_case_evaluation with stage final. Return only the requested JSON. Set mcpServer to rogueskills-cases and casePackRef to release-readiness@1.0.0." \
  >"$CODEX_EVENTS"

python3 - "$CODEX_RESULT" "$MCP_CONFIG" "$REPLAY_CASE_ID" <<'PY'
import json
import sys

result = json.load(open(sys.argv[1], encoding="utf-8"))
config = json.load(open(sys.argv[2], encoding="utf-8"))
replay_case_id = sys.argv[3]

expected = {
    "mcpServer": "rogueskills-cases",
    "casePackRef": "release-readiness@1.0.0",
    "mode": "verified_replay",
    "replayCaseId": replay_case_id,
    "status": "succeeded",
    "recommendation": "blocked",
    "runtimeVerified": True,
    "finalScore": 100.0,
    "hardGatesPassed": True,
    "sourceCount": 4,
    "factCount": 7,
    "checkRunCount": 19,
    "failedCaseIds": [],
}
for key, value in expected.items():
    if result.get(key) != value:
        raise SystemExit(f"Codex result mismatch for {key}: {result.get(key)!r} != {value!r}")
if not str(result.get("caseId", "")).startswith("case-run-"):
    raise SystemExit("Codex result did not contain a generated Case Run ID")
if config.get("name") != "rogueskills-cases" or not config.get("enabled"):
    raise SystemExit("Codex did not load the rogueskills-cases project MCP configuration")
transport = config.get("transport", {})
if transport.get("args") != ["-m", "rogueskills.mcp.case_bridge"]:
    raise SystemExit("Codex MCP configuration does not launch the generic Case Bridge")

print(json.dumps(result, ensure_ascii=False))
PY
