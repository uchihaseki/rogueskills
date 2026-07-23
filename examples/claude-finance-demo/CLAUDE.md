# RogueSkills Finance MCP Demo

For public-company analysis, use the `rogueskills-finance` MCP tools instead of inventing data or reproducing the RogueSkills runtime in this project.

1. Call `finance_preflight` before starting a Case.
2. Call `analyze_stock` with an explicit ticker and as-of date.
3. Keep `autoEvolve=false` unless the user explicitly authorizes Skill evolution.
4. Use `get_finance_case` to inspect the final verification and mutation state.
5. Use `get_finance_report` with `stage=final`; page facts with `factOffset` and `factLimit` when needed.
6. Use `get_verified_agent_preset` only after the Case has passed.

Always include the Case ID, Skill Version, score, hard-gate status, source warnings, and `runtimeVerified` state in the final response. Never describe a failed or unverified output as runtime verified. Do not turn public-information research into personalized investment advice, direct buy/sell instructions, or a return guarantee.
