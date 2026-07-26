from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from rogueskills.contracts.case_mcp import (
    CaseMcpCaseRequest,
    CaseMcpEmptyInput,
    CaseMcpEvaluationEnvelope,
    CaseMcpEvaluationRequest,
    CaseMcpPackDetail,
    CaseMcpPackList,
    CaseMcpPackRequest,
    CaseMcpPreflight,
    CaseMcpPreflightRequest,
    CaseMcpReportEnvelope,
    CaseMcpReportRequest,
    CaseMcpRunInput,
    CaseMcpRunSummary,
)
from rogueskills.contracts.case_validation_mcp import (
    CaseValidationMcpComparison,
    CaseValidationMcpContext,
    CaseValidationMcpDemoScript,
    CaseValidationMcpDetail,
    CaseValidationMcpEmptyInput,
    CaseValidationMcpList,
    CaseValidationMcpRequest,
    CaseValidationMcpRunRequest,
    CaseValidationMcpSummary,
    CaseValidationMcpValidateInput,
)
from rogueskills.contracts.demo_mcp import (
    DemoMcpContext,
    DemoMcpEmptyInput,
    DemoMcpEvolutionRunDetail,
    DemoMcpEvolutionRuns,
    DemoMcpInitialSkills,
    DemoMcpPresetDetail,
    DemoMcpPresetRequest,
    DemoMcpRunRequest,
    DemoMcpRunsRequest,
    DemoMcpSkillDetail,
    DemoMcpSkillRequest,
    DemoMcpSkillVersionDetail,
    DemoMcpSkillVersionRequest,
)
from rogueskills.contracts.finance_mcp import (
    FinanceMcpAnalyzeStockInput,
    FinanceMcpCaseRequest,
    FinanceMcpError,
    FinanceMcpPreflight,
    FinanceMcpPreflightInput,
    FinanceMcpPresetSummary,
    FinanceMcpReportEnvelope,
    FinanceMcpReportRequest,
    FinanceMcpRunSummary,
)

from .api_client import RogueSkillsApiClient, RogueSkillsApiError
from .protocol import McpTool, StdioMcpServer, run_stdio

LOCAL_READ_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
EXTERNAL_READ_ANNOTATIONS = {
    **LOCAL_READ_ANNOTATIONS,
    "openWorldHint": True,
}
NONDESTRUCTIVE_RUN_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}


class FinanceMcpBridge:
    def __init__(
        self,
        api: RogueSkillsApiClient,
        *,
        default_finance_skill_id: str | None = None,
        allowed_case_pack_ids: set[str] | frozenset[str] | None = None,
        default_case_skill_versions: dict[str, str] | None = None,
        server_name: str = "rogueskills-finance",
        include_demo_tools: bool = False,
    ) -> None:
        self.api = api
        self.default_finance_skill_id = (
            default_finance_skill_id or os.getenv("ROGUESKILLS_DEFAULT_FINANCE_SKILL_ID") or None
        )
        self.allowed_case_pack_ids = self._resolve_allowed_case_packs(allowed_case_pack_ids)
        self.default_case_skill_versions = self._resolve_default_case_skill_versions(
            default_case_skill_versions
        )
        tools = [
            McpTool(
                name="list_case_packs",
                description=(
                    "List only the RogueSkills Case Packs approved for this MCP host "
                    "project. The Bridge filters the server catalog through its allowlist."
                ),
                input_schema=CaseMcpEmptyInput.model_json_schema(),
                output_schema=CaseMcpPackList.model_json_schema(),
                handler=self.list_case_packs,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_pack",
                description=(
                    "Read the input schema, capabilities, runtime policy, and Skill admission "
                    "policy for one approved Case Pack."
                ),
                input_schema=CaseMcpPackRequest.model_json_schema(),
                output_schema=CaseMcpPackDetail.model_json_schema(),
                handler=self.get_case_pack,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="case_preflight",
                description=(
                    "Check an approved Case Pack's real Runtime and Provider readiness before "
                    "starting a Live Case."
                ),
                input_schema=CaseMcpPreflightRequest.model_json_schema(),
                output_schema=CaseMcpPreflight.model_json_schema(),
                handler=self.case_preflight,
                annotations=EXTERNAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="run_case",
                description=(
                    "Run an approved RogueSkills Case Pack through the generic Case API. "
                    "skillVersionId optionally pins execution; autoEvolve must be explicitly "
                    "authorized and cannot mutate a historical pinned version."
                ),
                input_schema=CaseMcpRunInput.model_json_schema(),
                output_schema=CaseMcpRunSummary.model_json_schema(),
                handler=self.run_case,
                annotations=NONDESTRUCTIVE_RUN_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_run",
                description=(
                    "Read a compact generic Case Run summary, including verification, "
                    "Mutation, score, outcome, Skill Version, and Artifact."
                ),
                input_schema=CaseMcpCaseRequest.model_json_schema(),
                output_schema=CaseMcpRunSummary.model_json_schema(),
                handler=self.get_case_run,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_report",
                description=(
                    "Read a baseline, evolved, or final typed Report for an approved Case Run. "
                    "Facts are paged and large optional sections are context-limited."
                ),
                input_schema=CaseMcpReportRequest.model_json_schema(),
                output_schema=CaseMcpReportEnvelope.model_json_schema(),
                handler=self.get_case_report,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_evaluation",
                description=(
                    "Read the authoritative Evaluation and hard-gate results for one stage of "
                    "an approved Case Run."
                ),
                input_schema=CaseMcpEvaluationRequest.model_json_schema(),
                output_schema=CaseMcpEvaluationEnvelope.model_json_schema(),
                handler=self.get_case_evaluation,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="list_initial_skills",
                description=(
                    "List compact summaries of the Initial Skill Library, including the "
                    "default local Awesome Finance Skills. Use get_skill for the selected "
                    "Skill's complete Genome."
                ),
                input_schema=DemoMcpEmptyInput.model_json_schema(),
                output_schema=DemoMcpInitialSkills.model_json_schema(),
                handler=self.list_initial_skills,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_skill",
                description=(
                    "Read one persisted Skill and its current Genome, workflow, constraints, "
                    "provenance, capability evidence, evaluations, and version lineage."
                ),
                input_schema=DemoMcpSkillRequest.model_json_schema(),
                output_schema=DemoMcpSkillDetail.model_json_schema(),
                handler=self.get_skill,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_skill_version",
                description=("Read one immutable Skill Version and its exact historical Genome."),
                input_schema=DemoMcpSkillVersionRequest.model_json_schema(),
                output_schema=DemoMcpSkillVersionDetail.model_json_schema(),
                handler=self.get_skill_version,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="list_evolution_runs",
                description=(
                    "List the most recently updated browser Evolution Runs as compact "
                    "summaries, including Skill, Mutation, Evolution, and AgentPreset IDs."
                ),
                input_schema=DemoMcpRunsRequest.model_json_schema(),
                output_schema=DemoMcpEvolutionRuns.model_json_schema(),
                handler=self.list_evolution_runs,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_evolution_run",
                description=(
                    "Read a complete browser Evolution Run plus the catalog details for its "
                    "accepted Mutations and unlocked Evolutions."
                ),
                input_schema=DemoMcpRunRequest.model_json_schema(),
                output_schema=DemoMcpEvolutionRunDetail.model_json_schema(),
                handler=self.get_evolution_run,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_agent_preset",
                description=(
                    "Read the candidate AgentPreset generated by an Evolution Run, addressed "
                    "by either presetId or runId. Preserve its runtimeVerified boundary."
                ),
                input_schema=DemoMcpPresetRequest.model_json_schema(),
                output_schema=DemoMcpPresetDetail.model_json_schema(),
                handler=self.get_agent_preset,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_demo_context",
                description=(
                    "Pick up the latest Evolution Run from the browser without copying IDs. "
                    "Returns its selected Skill, Run, Mutation/Evolution catalog, and "
                    "AgentPreset as one read-only demo context."
                ),
                input_schema=DemoMcpEmptyInput.model_json_schema(),
                output_schema=DemoMcpContext.model_json_schema(),
                handler=self.get_demo_context,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="list_case_validations",
                description=(
                    "List the persisted real Case validations for one browser Evolution Run, "
                    "including score delta, repaired gates, verification, acceptance, and promotion."
                ),
                input_schema=CaseValidationMcpRunRequest.model_json_schema(),
                output_schema=CaseValidationMcpList.model_json_schema(),
                handler=self.list_case_validations,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_latest_case_validation_context",
                description=(
                    "Discover the latest browser Evolution Run CaseValidation without asking "
                    "the user to copy a Run, Preset, Replay, or Validation ID."
                ),
                input_schema=CaseValidationMcpEmptyInput.model_json_schema(),
                output_schema=CaseValidationMcpContext.model_json_schema(),
                handler=self.get_latest_case_validation_context,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_validation_demo_script",
                description=(
                    "Generate a business-first Chinese talk track for the latest persisted "
                    "CaseValidation: company report first, then same-source A/B, Candidate "
                    "formation from Node History, associated repairs, and promotion boundaries."
                ),
                input_schema=CaseValidationMcpEmptyInput.model_json_schema(),
                output_schema=CaseValidationMcpDemoScript.model_json_schema(),
                handler=self.get_case_validation_demo_script,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="validate_evolution_run_on_case",
                description=(
                    "Create an idempotent Verified Replay A/B between a browser Evolution "
                    "Run's Base Skill Version and immutable Candidate AgentPreset. This may "
                    "promote an accepted Candidate to a new Runtime-bound Skill Version."
                ),
                input_schema=CaseValidationMcpValidateInput.model_json_schema(),
                output_schema=CaseValidationMcpSummary.model_json_schema(),
                handler=self.validate_evolution_run_on_case,
                annotations=NONDESTRUCTIVE_RUN_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_validation",
                description=(
                    "Read the complete persisted CaseValidation, including both business "
                    "Reports, Evaluations, source and dataset digests, and promotion evidence."
                ),
                input_schema=CaseValidationMcpRequest.model_json_schema(),
                output_schema=CaseValidationMcpDetail.model_json_schema(),
                handler=self.get_case_validation,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_case_validation_comparison",
                description=(
                    "Read the compact Baseline/Candidate comparison, repaired hard gates, "
                    "associated contributions, and promotion result for one CaseValidation."
                ),
                input_schema=CaseValidationMcpRequest.model_json_schema(),
                output_schema=CaseValidationMcpComparison.model_json_schema(),
                handler=self.get_case_validation_comparison,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="finance_preflight",
                description=(
                    "Check whether the real RogueSkills Finance Case Runtime, analyst, "
                    "and source policies are configured before starting an analysis."
                ),
                input_schema=FinanceMcpPreflightInput.model_json_schema(),
                output_schema=FinanceMcpPreflight.model_json_schema(),
                handler=self.finance_preflight,
                annotations=EXTERNAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="analyze_stock",
                description=(
                    "Run a real RogueSkills public-company Finance Case using the "
                    "configured analyst and approved public-data providers. autoEvolve "
                    "must be explicitly enabled when Skill mutation is authorized."
                ),
                input_schema=FinanceMcpAnalyzeStockInput.model_json_schema(),
                output_schema=FinanceMcpRunSummary.model_json_schema(),
                handler=self.analyze_stock,
                annotations=NONDESTRUCTIVE_RUN_ANNOTATIONS,
            ),
            McpTool(
                name="get_finance_case",
                description=(
                    "Read the compact state, verification result, Skill versions, mutation, "
                    "comparison, and AgentPreset summary for a Finance Case."
                ),
                input_schema=FinanceMcpCaseRequest.model_json_schema(),
                output_schema=FinanceMcpRunSummary.model_json_schema(),
                handler=self.get_finance_case,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_finance_report",
                description=(
                    "Read a baseline, evolved, or final evidence-bound Finance Report for "
                    "an existing Case. Prefer final unless explaining the evolution diff."
                ),
                input_schema=FinanceMcpReportRequest.model_json_schema(),
                output_schema=FinanceMcpReportEnvelope.model_json_schema(),
                handler=self.get_finance_report,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
            McpTool(
                name="get_verified_agent_preset",
                description=(
                    "Read the compact Runtime AgentPreset identity and digest produced by a "
                    "Finance Case that passed its evidence evaluation."
                ),
                input_schema=FinanceMcpCaseRequest.model_json_schema(),
                output_schema=FinanceMcpPresetSummary.model_json_schema(),
                handler=self.get_verified_agent_preset,
                annotations=LOCAL_READ_ANNOTATIONS,
            ),
        ]
        demo_tool_names = {
            "list_initial_skills",
            "get_skill",
            "get_skill_version",
            "list_evolution_runs",
            "get_evolution_run",
            "get_agent_preset",
            "get_demo_context",
            "list_case_validations",
            "get_latest_case_validation_context",
            "get_case_validation_demo_script",
            "validate_evolution_run_on_case",
            "get_case_validation",
            "get_case_validation_comparison",
        }
        if not include_demo_tools:
            tools = [tool for tool in tools if tool.name not in demo_tool_names]
        self.server = StdioMcpServer(
            name=server_name,
            version="0.2.0",
            instructions=(
                "Use only approved RogueSkills Case Packs. Call case_preflight before Live "
                "execution, keep autoEvolve disabled unless explicitly authorized, and never "
                "describe an output as runtime verified unless runtimeVerified=true. Finance "
                "aliases remain available for public-company analysis."
            ),
            tools=tools,
        )

    @staticmethod
    def _resolve_allowed_case_packs(
        explicit: set[str] | frozenset[str] | None,
    ) -> frozenset[str]:
        values = (
            explicit
            if explicit is not None
            else {
                item.strip()
                for item in os.getenv(
                    "ROGUESKILLS_ALLOWED_CASE_PACKS", "finance-stock-analysis"
                ).split(",")
                if item.strip()
            }
        )
        invalid = [item for item in values if not re.fullmatch(r"[a-z][a-z0-9-]{2,79}", item)]
        if invalid:
            raise ValueError(f"Invalid approved Case Pack ID: {invalid[0]}")
        return frozenset(values)

    def _ensure_case_pack_allowed(self, case_pack_id: str) -> None:
        if case_pack_id not in self.allowed_case_pack_ids:
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="CASE_PACK_NOT_APPROVED",
                    message="This Case Pack is not approved for the current MCP project.",
                    retryable=False,
                    details={"casePackId": case_pack_id},
                )
            )

    def _resolve_default_case_skill_versions(
        self, explicit: dict[str, str] | None
    ) -> dict[str, str]:
        if explicit is None:
            raw = os.getenv("ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS", "{}").strip()
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError as error:
                raise ValueError(
                    "ROGUESKILLS_DEFAULT_CASE_SKILL_VERSIONS must be a JSON object"
                ) from error
        else:
            parsed = explicit
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, str) and value.strip()
            for key, value in parsed.items()
        ):
            raise ValueError("Default Case Skill Versions must map Case Pack IDs to version IDs")
        normalized = {key.strip(): value.strip() for key, value in parsed.items()}
        unapproved = set(normalized) - set(self.allowed_case_pack_ids)
        if unapproved:
            raise ValueError(
                f"Default Skill Version configured for unapproved Case Pack: {sorted(unapproved)[0]}"
            )
        return normalized

    async def list_case_packs(self, arguments: dict[str, Any]) -> CaseMcpPackList:
        CaseMcpEmptyInput.model_validate(arguments)
        catalog = await self.api.list_case_packs()
        return CaseMcpPackList(
            casePacks=[item for item in catalog.casePacks if item.id in self.allowed_case_pack_ids]
        )

    async def get_case_pack(self, arguments: dict[str, Any]) -> CaseMcpPackDetail:
        request = CaseMcpPackRequest.model_validate(arguments)
        self._ensure_case_pack_allowed(request.casePackId)
        return await self.api.get_case_pack(request)

    async def case_preflight(self, arguments: dict[str, Any]) -> CaseMcpPreflight:
        request = CaseMcpPreflightRequest.model_validate(arguments)
        self._ensure_case_pack_allowed(request.casePackId)
        return await self.api.case_preflight(request)

    async def run_case(self, arguments: dict[str, Any]) -> CaseMcpRunSummary:
        resolved = dict(arguments)
        case_pack_id = resolved.get("casePackId")
        if (
            not resolved.get("skillVersionId")
            and isinstance(case_pack_id, str)
            and case_pack_id in self.default_case_skill_versions
        ):
            resolved["skillVersionId"] = self.default_case_skill_versions[case_pack_id]
        request = CaseMcpRunInput.model_validate(resolved)
        self._ensure_case_pack_allowed(request.casePackId)
        return await self.api.run_case(request)

    async def get_case_run(self, arguments: dict[str, Any]) -> CaseMcpRunSummary:
        request = CaseMcpCaseRequest.model_validate(arguments)
        result = await self.api.get_case_run(request)
        self._ensure_case_pack_allowed(result.casePackId)
        return result

    async def get_case_report(self, arguments: dict[str, Any]) -> CaseMcpReportEnvelope:
        request = CaseMcpReportRequest.model_validate(arguments)
        run = await self.api.get_case_run(CaseMcpCaseRequest(caseId=request.caseId))
        self._ensure_case_pack_allowed(run.casePackId)
        return await self.api.get_case_report(request)

    async def get_case_evaluation(self, arguments: dict[str, Any]) -> CaseMcpEvaluationEnvelope:
        request = CaseMcpEvaluationRequest.model_validate(arguments)
        run = await self.api.get_case_run(CaseMcpCaseRequest(caseId=request.caseId))
        self._ensure_case_pack_allowed(run.casePackId)
        return await self.api.get_case_evaluation(request)

    async def list_initial_skills(self, arguments: dict[str, Any]) -> DemoMcpInitialSkills:
        request = DemoMcpEmptyInput.model_validate(arguments)
        return await self.api.list_initial_skills(request)

    async def get_skill(self, arguments: dict[str, Any]) -> DemoMcpSkillDetail:
        request = DemoMcpSkillRequest.model_validate(arguments)
        return await self.api.get_skill(request)

    async def get_skill_version(self, arguments: dict[str, Any]) -> DemoMcpSkillVersionDetail:
        request = DemoMcpSkillVersionRequest.model_validate(arguments)
        return await self.api.get_skill_version(request)

    async def list_evolution_runs(self, arguments: dict[str, Any]) -> DemoMcpEvolutionRuns:
        request = DemoMcpRunsRequest.model_validate(arguments)
        return await self.api.list_evolution_runs(request)

    async def get_evolution_run(self, arguments: dict[str, Any]) -> DemoMcpEvolutionRunDetail:
        request = DemoMcpRunRequest.model_validate(arguments)
        return await self.api.get_evolution_run(request)

    async def get_agent_preset(self, arguments: dict[str, Any]) -> DemoMcpPresetDetail:
        request = DemoMcpPresetRequest.model_validate(arguments)
        return await self.api.get_agent_preset(request)

    async def get_demo_context(self, arguments: dict[str, Any]) -> DemoMcpContext:
        request = DemoMcpEmptyInput.model_validate(arguments)
        return await self.api.get_demo_context(request)

    async def list_case_validations(self, arguments: dict[str, Any]) -> CaseValidationMcpList:
        request = CaseValidationMcpRunRequest.model_validate(arguments)
        return await self.api.list_case_validations(request)

    async def get_latest_case_validation_context(
        self, arguments: dict[str, Any]
    ) -> CaseValidationMcpContext:
        request = CaseValidationMcpEmptyInput.model_validate(arguments)
        return await self.api.get_latest_case_validation_context(request)

    async def get_case_validation_demo_script(
        self, arguments: dict[str, Any]
    ) -> CaseValidationMcpDemoScript:
        request = CaseValidationMcpEmptyInput.model_validate(arguments)
        return await self.api.get_case_validation_demo_script(request)

    async def validate_evolution_run_on_case(
        self, arguments: dict[str, Any]
    ) -> CaseValidationMcpSummary:
        request = CaseValidationMcpValidateInput.model_validate(arguments)
        self._ensure_case_pack_allowed(request.casePackId)
        return await self.api.validate_evolution_run_on_case(request)

    async def get_case_validation(self, arguments: dict[str, Any]) -> CaseValidationMcpDetail:
        return await self.api.get_case_validation(
            CaseValidationMcpRequest.model_validate(arguments)
        )

    async def get_case_validation_comparison(
        self, arguments: dict[str, Any]
    ) -> CaseValidationMcpComparison:
        return await self.api.get_case_validation_comparison(
            CaseValidationMcpRequest.model_validate(arguments)
        )

    async def finance_preflight(self, arguments: dict[str, Any]) -> FinanceMcpPreflight:
        self._ensure_case_pack_allowed("finance-stock-analysis")
        FinanceMcpPreflightInput.model_validate(arguments)
        return await self.api.finance_preflight()

    async def analyze_stock(self, arguments: dict[str, Any]) -> FinanceMcpRunSummary:
        self._ensure_case_pack_allowed("finance-stock-analysis")
        resolved = dict(arguments)
        if not resolved.get("skillId") and self.default_finance_skill_id:
            resolved["skillId"] = self.default_finance_skill_id
        return await self.api.analyze_stock(FinanceMcpAnalyzeStockInput.model_validate(resolved))

    async def get_finance_case(self, arguments: dict[str, Any]) -> FinanceMcpRunSummary:
        self._ensure_case_pack_allowed("finance-stock-analysis")
        return await self.api.get_finance_case(FinanceMcpCaseRequest.model_validate(arguments))

    async def get_finance_report(self, arguments: dict[str, Any]) -> FinanceMcpReportEnvelope:
        self._ensure_case_pack_allowed("finance-stock-analysis")
        return await self.api.get_finance_report(FinanceMcpReportRequest.model_validate(arguments))

    async def get_verified_agent_preset(self, arguments: dict[str, Any]) -> FinanceMcpPresetSummary:
        self._ensure_case_pack_allowed("finance-stock-analysis")
        return await self.api.get_verified_agent_preset(
            FinanceMcpCaseRequest.model_validate(arguments)
        )

    async def close(self) -> None:
        await self.api.close()


async def _run() -> None:
    bridge = FinanceMcpBridge(RogueSkillsApiClient.from_environment())
    try:
        await run_stdio(bridge.server)
    finally:
        await bridge.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
