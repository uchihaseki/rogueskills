#!/bin/zsh
set -euo pipefail

ROOT="/Users/shuo/workspace/code/rogueskills"
DEMO="$ROOT/examples/claude-finance-demo"
ARTIFACTS="$ROOT/artifacts/finance-e2e-20260722"
DATABASE="$ARTIFACTS/prior-real.db"
API_LOG="$ARTIFACTS/40-claude-mcp-api.log"
CLAUDE_OUTPUT="$ARTIFACTS/41-claude-mcp-aapl-transcript.json"
CLAUDE_DEBUG="$ARTIFACTS/42-claude-mcp-debug.log"

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
claude --print \
  --output-format json \
  --permission-mode dontAsk \
  --strict-mcp-config \
  --mcp-config .mcp.json \
  --debug-file "$CLAUDE_DEBUG" \
  --no-session-persistence \
  "Use RogueSkills MCP to run a verified replay for AAPL as of 2026-07-21. Use replay Case ID finance-case-6266b782a74c416ea985aa35031aee9d, keep auto evolution disabled, call the MCP tools rather than inventing data, and report the resulting Case ID, Skill Version, score, hard-gate state, source count, fact count, and runtimeVerified." \
  >"$CLAUDE_OUTPUT"

python3 - "$CLAUDE_OUTPUT" <<'PY'
import json
import re
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
text = json.dumps(payload, ensure_ascii=False)
if "runtimeVerified" not in text or "true" not in text.lower():
    raise SystemExit("Claude transcript did not report runtimeVerified=true")
if not re.search(r"finance-case-[A-Za-z0-9._-]+", text):
    raise SystemExit("Claude transcript did not contain a Finance Case ID")
print(text)
PY
