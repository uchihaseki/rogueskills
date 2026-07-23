# RogueSkills Generic Case MCP Demo

Use the `rogueskills-cases` MCP tools for approved RogueSkills Case Packs instead of
inventing provider data or reproducing the Runtime in this project.

1. Call `list_case_packs` and confirm the requested Pack is visible.
2. Call `get_case_pack` and `case_preflight` before a Live run.
3. Call `run_case` with an explicit `casePackId`, `skillId`, and typed `input`.
4. Keep `autoEvolve=false` unless the user explicitly authorizes Skill evolution.
5. Use `get_case_run`, `get_case_report`, and `get_case_evaluation` for the final evidence.
6. Use `skillVersionId` when the user asks for a reproducible pinned run.

Always include the Case ID, Case Pack version, Skill Version, score, hard-gate status,
outcome, source count, and `runtimeVerified` state. A `blocked` or `review` outcome can
still be runtime verified when the evidence and evaluation are complete. Never describe
failed or unverified output as verified. Never use a Case Pack that is absent from the
allowlisted catalog.
