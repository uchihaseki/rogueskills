# Awesome Finance Skills Codex Demo

This project is the Codex side of the browser-to-Codex self-evolution demo.
The browser seeds the local Awesome Finance Skills snapshot automatically, and
the MCP bridge reads the resulting Skill and Evolution Run from the same API.

After the presenter finishes an Evolution Run in the browser:

1. Call `get_demo_context` first. It discovers the latest local Run without
   requiring the presenter to copy an opaque Run ID.
2. Use `get_skill` or `get_skill_version` to explain the selected Genome,
   workflow, constraints, provenance, and version lineage.
3. Use `get_evolution_run` to explain accepted Mutation trade-offs and unlocked
   Evolutions.
4. Use `get_agent_preset` to inspect the generated candidate runtime config.
5. Preserve the `runtimeVerified` value exactly. A browser Evolution artifact
   uses capability simulation and must not be described as a real finance-case
   runtime verification.

Do not invent Skill or Run state. If `get_demo_context` reports `available=false`,
ask the presenter to select an Initial Skill and run the browser flow first.
