from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx

from rogueskills.contracts.case_mcp import (
    CaseMcpCaseRequest,
    CaseMcpEvaluation,
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
    build_case_mcp_report,
    summarize_case_run,
)
from rogueskills.contracts.demo_mcp import (
    DemoMcpContext,
    DemoMcpEmptyInput,
    DemoMcpEvolutionRunDetail,
    DemoMcpEvolutionRuns,
    DemoMcpEvolutionRunSummary,
    DemoMcpInitialSkills,
    DemoMcpPresetDetail,
    DemoMcpPresetRequest,
    DemoMcpRunRequest,
    DemoMcpRunsRequest,
    DemoMcpSkillDetail,
    DemoMcpSkillRequest,
    DemoMcpSkillSummary,
    DemoMcpSkillVersionDetail,
    DemoMcpSkillVersionRequest,
)
from rogueskills.contracts.finance_mcp import (
    FinanceMcpAnalyzeStockInput,
    FinanceMcpCaseRequest,
    FinanceMcpError,
    FinanceMcpLimits,
    FinanceMcpPreflight,
    FinanceMcpPresetSummary,
    FinanceMcpReportEnvelope,
    FinanceMcpReportRequest,
    FinanceMcpRunSummary,
    build_finance_mcp_report,
    finance_mcp_error_from_api,
    summarize_finance_case,
    summarize_finance_preset,
)


class RogueSkillsApiError(RuntimeError):
    def __init__(self, error: FinanceMcpError) -> None:
        super().__init__(error.message)
        self.error = error


def normalize_api_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("RogueSkills API base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("RogueSkills API credentials must not be embedded in the URL")
    if parsed.query or parsed.fragment:
        raise ValueError("RogueSkills API base URL must not contain a query or fragment")
    return normalized


class RogueSkillsApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        limits: FinanceMcpLimits | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_api_base_url(base_url)
        self.limits = limits or FinanceMcpLimits()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.limits.readTimeoutMs / 1000),
            transport=transport,
            headers={"User-Agent": "RogueSkills-Case-MCP/0.2"},
        )

    @classmethod
    def from_environment(cls) -> RogueSkillsApiClient:
        return cls(base_url=os.getenv("ROGUESKILLS_API_BASE_URL", "http://127.0.0.1:5173"))

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_initial_skills(self, _request: DemoMcpEmptyInput) -> DemoMcpInitialSkills:
        payload = await self._request_json(
            "GET", "/api/library/initial", timeout_ms=self.limits.readTimeoutMs
        )
        summaries: list[DemoMcpSkillSummary] = []
        for item in payload.get("skills", []):
            if not isinstance(item, dict):
                continue
            genome = item.get("genome") if isinstance(item.get("genome"), dict) else {}
            metadata = genome.get("metadata") if isinstance(genome.get("metadata"), dict) else {}
            evaluation = (
                genome.get("evaluation") if isinstance(genome.get("evaluation"), dict) else {}
            )
            summaries.append(
                DemoMcpSkillSummary(
                    id=str(item["id"]),
                    name=str(item.get("name") or genome.get("name") or item["id"]),
                    description=str(item.get("description") or genome.get("description") or ""),
                    status=str(item.get("status") or "initial"),
                    currentVersionId=item.get("currentVersionId"),
                    sourceId=item.get("sourceId"),
                    category=str(metadata["category"]) if metadata.get("category") else None,
                    score=(
                        float(evaluation["score"]) if evaluation.get("score") is not None else None
                    ),
                )
            )
        return DemoMcpInitialSkills(skills=summaries)

    async def get_skill(self, request: DemoMcpSkillRequest) -> DemoMcpSkillDetail:
        payload = await self._request_json(
            "GET",
            f"/api/skills/{quote(request.skillId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return DemoMcpSkillDetail.model_validate(payload)

    async def get_skill_version(
        self, request: DemoMcpSkillVersionRequest
    ) -> DemoMcpSkillVersionDetail:
        payload = await self._request_json(
            "GET",
            f"/api/skill-versions/{quote(request.skillVersionId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return DemoMcpSkillVersionDetail.model_validate(payload)

    @staticmethod
    def _evolution_summary(record: dict[str, Any]) -> DemoMcpEvolutionRunSummary:
        run = record.get("run") if isinstance(record.get("run"), dict) else {}
        artifact = record.get("artifact") if isinstance(record.get("artifact"), dict) else {}
        automation = run.get("automation") if isinstance(run.get("automation"), dict) else {}
        node_count = sum(
            len(layer)
            for region in run.get("map", [])
            if isinstance(region, dict)
            for layer in region.get("layers", [])
            if isinstance(layer, list)
        )
        evidence = artifact.get("evaluationEvidence") if isinstance(artifact, dict) else {}
        return DemoMcpEvolutionRunSummary(
            id=str(run.get("id", "")),
            status=str(run.get("status", "unknown")),
            phase=str(run.get("phase", "unknown")),
            seed=str(run.get("seed", "")),
            baseSkillId=str(run.get("baseSkillId", "")),
            baseSkillVersionId=record.get("baseSkillVersionId"),
            skillName=run.get("skillName"),
            scenarioId=run.get("scenarioId"),
            mutationIds=[str(item) for item in run.get("mutationIds", [])],
            evolutionIds=[str(item) for item in run.get("evolutionIds", [])],
            completedNodeCount=len(run.get("completedNodeIds", [])),
            totalNodeCount=node_count,
            automationStatus=automation.get("status"),
            artifactId=artifact.get("id"),
            runtimeVerified=bool(evidence.get("runtimeVerified", False)),
        )

    async def list_evolution_runs(self, request: DemoMcpRunsRequest) -> DemoMcpEvolutionRuns:
        query = f"/api/runs?limit={request.limit}"
        if request.status:
            query += f"&status={quote(request.status, safe='')}"
        payload = await self._request_json("GET", query, timeout_ms=self.limits.readTimeoutMs)
        return DemoMcpEvolutionRuns(
            runs=[
                self._evolution_summary(item)
                for item in payload.get("runs", [])
                if isinstance(item, dict)
            ]
        )

    async def get_evolution_run(self, request: DemoMcpRunRequest) -> DemoMcpEvolutionRunDetail:
        record = await self._request_json(
            "GET",
            f"/api/runs/{quote(request.runId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        catalog = await self._request_json(
            "GET", "/api/evolution/catalog", timeout_ms=self.limits.readTimeoutMs
        )
        run = record.get("run") if isinstance(record.get("run"), dict) else {}
        mutation_ids = set(run.get("mutationIds", []))
        evolution_ids = set(run.get("evolutionIds", []))
        mutation_details = [
            item
            for item in catalog.get("mutations", [])
            if isinstance(item, dict) and item.get("id") in mutation_ids
        ]
        evolution_details = [
            item
            for item in catalog.get("evolutions", [])
            if isinstance(item, dict) and item.get("id") in evolution_ids
        ]
        return DemoMcpEvolutionRunDetail(
            record=record,
            mutationDetails=mutation_details,
            evolutionDetails=evolution_details,
        )

    async def get_agent_preset(self, request: DemoMcpPresetRequest) -> DemoMcpPresetDetail:
        if request.presetId:
            path = f"/api/agent-presets/{quote(request.presetId, safe='')}"
        elif request.runId:
            path = f"/api/runs/{quote(request.runId, safe='')}"
        else:
            raise ValueError("presetId or runId is required")
        payload = await self._request_json("GET", path, timeout_ms=self.limits.readTimeoutMs)
        if request.runId:
            preset = payload.get("artifact")
            if not isinstance(preset, dict):
                raise RogueSkillsApiError(
                    FinanceMcpError(
                        code="AGENT_PRESET_NOT_AVAILABLE",
                        message="该 Evolution Run 尚未生成 AgentPreset。",
                        retryable=False,
                    )
                )
            return DemoMcpPresetDetail(preset=preset)
        return DemoMcpPresetDetail.model_validate(payload)

    async def get_demo_context(self, _request: DemoMcpEmptyInput) -> DemoMcpContext:
        payload = await self._request_json(
            "GET", "/api/demo/context", timeout_ms=self.limits.readTimeoutMs
        )
        return DemoMcpContext.model_validate(payload)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout_ms: int,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_id = f"mcp-{uuid4().hex}"
        try:
            response = await self._client.request(
                method,
                path,
                json=json,
                timeout=timeout_ms / 1000,
                headers={"X-Request-ID": request_id},
            )
        except httpx.TimeoutException as error:
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_API_TIMEOUT",
                    message="RogueSkills API did not complete within the configured timeout.",
                    retryable=True,
                    details={"timeoutMs": timeout_ms},
                    requestId=request_id,
                )
            ) from error
        except httpx.RequestError as error:
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_API_UNREACHABLE",
                    message="RogueSkills API could not be reached.",
                    retryable=True,
                    details={"reason": type(error).__name__},
                    requestId=request_id,
                )
            ) from error

        response_request_id = response.headers.get("X-Request-ID") or request_id
        try:
            payload = response.json()
        except ValueError as error:
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API returned a non-JSON response.",
                    retryable=response.status_code >= 500,
                    details={"statusCode": response.status_code},
                    requestId=response_request_id,
                )
            ) from error

        if not response.is_success:
            raise RogueSkillsApiError(
                finance_mcp_error_from_api(
                    payload,
                    status_code=response.status_code,
                    request_id=response_request_id,
                )
            )
        if not isinstance(payload, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API returned an invalid JSON object.",
                    retryable=False,
                    details={"statusCode": response.status_code},
                    requestId=response_request_id,
                )
            )
        return payload

    async def finance_preflight(self) -> FinanceMcpPreflight:
        payload = await self._request_json(
            "GET",
            "/api/finance/cases/preflight",
            timeout_ms=self.limits.preflightTimeoutMs,
        )
        return FinanceMcpPreflight.model_validate(payload)

    async def list_case_packs(self) -> CaseMcpPackList:
        payload = await self._request_json(
            "GET",
            "/api/case-packs",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return CaseMcpPackList.model_validate(payload)

    async def get_case_pack(self, request: CaseMcpPackRequest) -> CaseMcpPackDetail:
        path = f"/api/case-packs/{quote(request.casePackId, safe='')}"
        if request.casePackVersion:
            path = f"{path}?version={quote(request.casePackVersion, safe='')}"
        payload = await self._request_json(
            "GET",
            path,
            timeout_ms=self.limits.readTimeoutMs,
        )
        return CaseMcpPackDetail.model_validate(payload)

    async def case_preflight(self, request: CaseMcpPreflightRequest) -> CaseMcpPreflight:
        path = f"/api/case-runs/preflight?casePackId={quote(request.casePackId, safe='')}"
        if request.casePackVersion:
            path = f"{path}&casePackVersion={quote(request.casePackVersion, safe='')}"
        payload = await self._request_json(
            "GET",
            path,
            timeout_ms=self.limits.preflightTimeoutMs,
        )
        details = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "casePackId",
                "casePackVersion",
                "ready",
                "runtime",
                "sources",
            }
        }
        return CaseMcpPreflight(
            casePackId=str(payload["casePackId"]),
            casePackVersion=str(payload["casePackVersion"]),
            ready=bool(payload["ready"]),
            runtime=str(payload["runtime"]) if payload.get("runtime") else None,
            sources=list(payload.get("sources", [])),
            details=details,
        )

    @staticmethod
    def _case_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
        case = payload.get("caseRun")
        if not isinstance(case, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API response does not contain a Case Run.",
                    retryable=False,
                )
            )
        return case

    async def run_case(self, request: CaseMcpRunInput) -> CaseMcpRunSummary:
        payload = await self._request_json(
            "POST",
            "/api/case-runs",
            timeout_ms=self.limits.caseExecutionTimeoutMs,
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return summarize_case_run(self._case_run_payload(payload))

    async def get_case_run(self, request: CaseMcpCaseRequest) -> CaseMcpRunSummary:
        case = await self.get_case_run_state(request)
        return summarize_case_run(case)

    async def get_case_run_state(self, request: CaseMcpCaseRequest) -> dict[str, Any]:
        payload = await self._request_json(
            "GET",
            f"/api/case-runs/{quote(request.caseId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return self._case_run_payload(payload)

    async def get_case_report(self, request: CaseMcpReportRequest) -> CaseMcpReportEnvelope:
        case = await self.get_case_run_state(CaseMcpCaseRequest(caseId=request.caseId))
        return build_case_mcp_report(
            case,
            request.stage,
            fact_offset=request.factOffset,
            fact_limit=request.factLimit,
            limits=self.limits,
        )

    async def get_case_evaluation(
        self, request: CaseMcpEvaluationRequest
    ) -> CaseMcpEvaluationEnvelope:
        case = await self.get_case_run_state(CaseMcpCaseRequest(caseId=request.caseId))
        if request.stage == "final":
            raw_evaluation = case.get("finalEvaluation")
        else:
            section = case.get(request.stage)
            raw_evaluation = section.get("evaluation") if isinstance(section, dict) else None
        if not isinstance(raw_evaluation, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="CASE_EVALUATION_NOT_AVAILABLE",
                    message="The requested Case evaluation is not available.",
                    retryable=False,
                    caseId=request.caseId,
                    details={"stage": request.stage},
                )
            )
        return CaseMcpEvaluationEnvelope(
            caseId=request.caseId,
            casePackId=str(case["casePackId"]),
            casePackVersion=str(case["casePackVersion"]),
            stage=request.stage,
            evaluation=CaseMcpEvaluation.model_validate(raw_evaluation),
        )

    @staticmethod
    def _case_payload(payload: dict[str, Any]) -> dict[str, Any]:
        case = payload.get("case")
        if not isinstance(case, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API response does not contain a Finance Case.",
                    retryable=False,
                )
            )
        return case

    async def analyze_stock(self, request: FinanceMcpAnalyzeStockInput) -> FinanceMcpRunSummary:
        if not request.skillId:
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="FINANCE_SKILL_ID_REQUIRED",
                    message=(
                        "No Finance Skill was supplied and the MCP Bridge has no approved "
                        "default Finance Skill."
                    ),
                    retryable=False,
                )
            )
        payload = await self._request_json(
            "POST",
            "/api/finance/cases",
            timeout_ms=self.limits.caseExecutionTimeoutMs,
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return summarize_finance_case(self._case_payload(payload))

    async def get_finance_case(self, request: FinanceMcpCaseRequest) -> FinanceMcpRunSummary:
        payload = await self._request_json(
            "GET",
            f"/api/finance/cases/{quote(request.caseId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return summarize_finance_case(self._case_payload(payload))

    async def get_finance_report(
        self, request: FinanceMcpReportRequest
    ) -> FinanceMcpReportEnvelope:
        payload = await self._request_json(
            "GET",
            f"/api/finance/cases/{quote(request.caseId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return build_finance_mcp_report(
            self._case_payload(payload),
            request.stage,
            fact_offset=request.factOffset,
            fact_limit=request.factLimit,
            limits=self.limits,
        )

    async def get_verified_agent_preset(
        self, request: FinanceMcpCaseRequest
    ) -> FinanceMcpPresetSummary:
        payload = await self._request_json(
            "GET",
            f"/api/finance/cases/{quote(request.caseId, safe='')}/agent-preset",
            timeout_ms=self.limits.readTimeoutMs,
        )
        preset = payload.get("preset")
        if not isinstance(preset, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API response does not contain an AgentPreset.",
                    retryable=False,
                )
            )
        return summarize_finance_preset(preset)
