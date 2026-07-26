from __future__ import annotations

import asyncio
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
    summarize_case_validation,
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

    @staticmethod
    def _validation_payload(payload: dict[str, Any]) -> dict[str, Any]:
        validation = payload.get("validation")
        if not isinstance(validation, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="ROGUESKILLS_INVALID_RESPONSE",
                    message="RogueSkills API response does not contain a CaseValidation.",
                    retryable=False,
                )
            )
        return validation

    async def list_case_validations(
        self, request: CaseValidationMcpRunRequest
    ) -> CaseValidationMcpList:
        payload = await self._request_json(
            "GET",
            f"/api/runs/{quote(request.runId, safe='')}/case-validations?limit={request.limit}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return CaseValidationMcpList(
            validations=[
                summarize_case_validation(item)
                for item in payload.get("validations", [])
                if isinstance(item, dict)
            ]
        )

    async def get_case_validation(
        self, request: CaseValidationMcpRequest
    ) -> CaseValidationMcpDetail:
        payload = await self._request_json(
            "GET",
            f"/api/case-validations/{quote(request.validationId, safe='')}",
            timeout_ms=self.limits.readTimeoutMs,
        )
        return CaseValidationMcpDetail(validation=self._validation_payload(payload))

    async def get_case_validation_comparison(
        self, request: CaseValidationMcpRequest
    ) -> CaseValidationMcpComparison:
        detail = await self.get_case_validation(request)
        validation = detail.validation
        comparison = validation.get("comparison")
        if not isinstance(comparison, dict):
            raise RogueSkillsApiError(
                FinanceMcpError(
                    code="CASE_VALIDATION_COMPARISON_NOT_AVAILABLE",
                    message="The CaseValidation comparison is not available yet.",
                    retryable=validation.get("status") in {"queued", "running"},
                    details={"validationId": request.validationId},
                )
            )
        return CaseValidationMcpComparison(
            validationId=request.validationId,
            comparison=comparison,
            contributionCoverage=list(validation.get("contributionCoverage", [])),
            promotion=dict(validation.get("promotion") or {}),
        )

    async def validate_evolution_run_on_case(
        self, request: CaseValidationMcpValidateInput
    ) -> CaseValidationMcpSummary:
        payload = await self._request_json(
            "POST",
            f"/api/runs/{quote(request.runId, safe='')}/case-validations",
            timeout_ms=self.limits.readTimeoutMs,
            json={
                "casePackId": request.casePackId,
                "casePackVersion": request.casePackVersion,
                "mode": request.mode,
                "replayCaseId": request.replayCaseId,
                "input": request.input,
            },
        )
        validation = self._validation_payload(payload)
        deadline = asyncio.get_running_loop().time() + self.limits.caseExecutionTimeoutMs / 1000
        while validation.get("status") in {"queued", "running"}:
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.1)
            validation = (
                await self.get_case_validation(
                    CaseValidationMcpRequest(validationId=str(validation["id"]))
                )
            ).validation
        return summarize_case_validation(validation)

    async def get_latest_case_validation_context(
        self, _request: CaseValidationMcpEmptyInput
    ) -> CaseValidationMcpContext:
        payload = await self._request_json(
            "GET", "/api/runs?limit=20&status=victory", timeout_ms=self.limits.readTimeoutMs
        )
        candidates: list[CaseValidationMcpSummary] = []
        for record in payload.get("runs", []):
            if not isinstance(record, dict) or not isinstance(record.get("run"), dict):
                continue
            run_id = str(record["run"].get("id") or "")
            if not run_id:
                continue
            validations = await self.list_case_validations(
                CaseValidationMcpRunRequest(runId=run_id, limit=20)
            )
            candidates.extend(validations.validations)
        if candidates:
            latest = max(
                candidates,
                key=lambda item: (item.createdAt, item.validationId),
            )
            return CaseValidationMcpContext(
                available=True,
                message="Latest browser Evolution Run CaseValidation context.",
                validation=latest,
            )
        return CaseValidationMcpContext(
            available=False,
            message="No CaseValidation is available. Run the browser Evolution and Verified Replay validation first.",
            validation=None,
        )

    async def get_case_validation_demo_script(
        self, _request: CaseValidationMcpEmptyInput
    ) -> CaseValidationMcpDemoScript:
        latest = await self.get_latest_case_validation_context(CaseValidationMcpEmptyInput())
        if not latest.available or latest.validation is None:
            return CaseValidationMcpDemoScript(
                available=False,
                message="No CaseValidation is available for a business-first demo script.",
            )
        summary = latest.validation
        detail = await self.get_case_validation(
            CaseValidationMcpRequest(validationId=summary.validationId)
        )
        validation = detail.validation
        run_detail = await self.get_evolution_run(DemoMcpRunRequest(runId=summary.sourceRunId))
        run = run_detail.record.get("run")
        run = run if isinstance(run, dict) else {}
        mutations = {
            str(item.get("id")): item
            for item in run_detail.mutationDetails
            if isinstance(item, dict) and item.get("id")
        }
        evolutions = {
            str(item.get("id")): item
            for item in run_detail.evolutionDetails
            if isinstance(item, dict) and item.get("id")
        }
        candidate = validation.get("candidate")
        candidate = candidate if isinstance(candidate, dict) else {}
        report = candidate.get("report")
        report = report if isinstance(report, dict) else {}
        narrative = report.get("narrative")
        narrative = narrative if isinstance(narrative, dict) else {}
        business_report = {
            "company": report.get("company"),
            "asOfDate": report.get("asOfDate"),
            "summary": narrative.get("summary"),
            "findings": list(narrative.get("findings") or []),
            "risks": list(narrative.get("risks") or []),
            "dataGaps": list(narrative.get("dataGaps") or []),
            "conclusionBoundary": narrative.get("conclusionBoundary"),
            "sourceCount": len(report.get("sources") or []),
        }
        formation: list[dict[str, Any]] = []
        for item in run.get("nodeHistory", []):
            if not isinstance(item, dict):
                continue
            reward = item.get("reward") if isinstance(item.get("reward"), dict) else {}
            mutation_id = reward.get("selectedMutationId")
            evolution_ids = [str(value) for value in reward.get("unlockedEvolutionIds", [])]
            if not mutation_id and not evolution_ids and item.get("status") == "entered":
                continue
            formation.append(
                {
                    "sequence": item.get("sequence"),
                    "nodeId": item.get("nodeId"),
                    "status": item.get("status"),
                    "regionName": item.get("regionName"),
                    "testType": item.get("type"),
                    "selectedMutationId": mutation_id,
                    "selectedMutationName": (mutations.get(str(mutation_id)) or {}).get("name")
                    if mutation_id
                    else None,
                    "unlockedEvolutions": [
                        {
                            "id": evolution_id,
                            "name": (evolutions.get(evolution_id) or {}).get("name"),
                        }
                        for evolution_id in evolution_ids
                    ],
                    "legacyIncomplete": bool(item.get("legacyIncomplete", False)),
                }
            )
        comparison = validation.get("comparison")
        comparison = comparison if isinstance(comparison, dict) else {}
        promotion = validation.get("promotion")
        promotion = promotion if isinstance(promotion, dict) else {}
        company = business_report.get("company")
        company_name = company.get("name") if isinstance(company, dict) else "目标公司"
        talk_track = [
            f"先展示 {company_name} 的候选研究报告、主要发现、风险和结论边界。",
            (
                f"说明这是 Verified Replay：基础版本 {summary.baseSkillVersionId} 与候选预设 "
                f"{summary.candidatePresetId} 共用锁定的来源、数据集、模型和预算。"
            ),
            (
                f"对比基线 {comparison.get('baselineScore', '—')} 分与候选 "
                f"{comparison.get('candidateScore', '—')} 分，严格提升 "
                f"{comparison.get('scoreDelta', '—')} 分。"
            ),
            "按节点历史解释候选配置中已选择的优化项和解锁的能力组合。",
            (
                f"最后分别报告 runtimeVerified={bool(validation.get('runtimeVerified'))}、"
                f"accepted={bool(validation.get('accepted'))}、"
                f"promoted={bool(promotion.get('promoted'))}。"
            ),
        ]
        return CaseValidationMcpDemoScript(
            available=True,
            message="Business-first CaseValidation demo script generated from persisted evidence.",
            validationId=summary.validationId,
            sourceRunId=summary.sourceRunId,
            evidenceMode="verified_replay",
            businessReport=business_report,
            comparison=comparison,
            candidateFormation=formation,
            associatedRepairs=list(validation.get("contributionCoverage") or []),
            promotion=promotion,
            talkTrack=talk_track,
            boundaries=[
                "Verified Replay 使用持久化真实来源快照，不等同于现场 Live 请求。",
                "节点优化项与门槛修复属于 associated_not_causal，不代表单项独立因果。",
                "runtimeVerified、accepted 和 promoted 必须分别陈述。",
            ],
        )

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
