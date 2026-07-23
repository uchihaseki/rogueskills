# RogueSkills Generic Case MCP Demo

Use the approved `rogueskills-cases` MCP server for RogueSkills Case Packs. Do
not invent provider data or reproduce the Runtime in this project.

1. Call `list_case_packs` and confirm the requested Pack is allowlisted.
2. Call `get_case_pack` and `case_preflight` before a Live or Verified Replay run.
3. Call `run_case` with an explicit `casePackId`, typed `input`, and `autoEvolve=false`.
4. Use `get_case_run`, `get_case_report`, and `get_case_evaluation` for final evidence.
5. Preserve the Case ID, Pack version, Skill Version, score, hard-gate status, outcome,
   source count, and `runtimeVerified` state in the final response.

A `blocked` or `review` recommendation can still be runtime verified when its evidence
and evaluation are complete. Never describe failed or unverified output as verified, and
never use a Case Pack that is absent from the allowlisted catalog.
