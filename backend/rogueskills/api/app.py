from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import ValidationError

from rogueskills.adapters.agent_preset_exporter import (
    AgentPresetExportTarget,
    build_agent_preset_export,
)
from rogueskills.adapters.agent_preset_loader import (
    AgentPresetIntegrityError,
    load_agent_preset,
)
from rogueskills.adapters.discovery_gateway import DiscoveryGateway
from rogueskills.adapters.finance_data import SecFinanceDataGateway
from rogueskills.adapters.github_release_data import GithubReleaseReadinessGateway
from rogueskills.adapters.llm_finance_analyst import OpenAICompatibleFinanceAnalyst
from rogueskills.adapters.llm_material_normalizer import OpenAICompatibleMaterialNormalizer
from rogueskills.agents.finance_analyst import FinanceAnalyst, UnavailableFinanceAnalyst
from rogueskills.agents.finance_demo_analyst import DemoFinanceAnalyst
from rogueskills.agents.material_normalizer import MaterialNormalizer, UnavailableMaterialNormalizer
from rogueskills.application.awesome_finance_import import AwesomeFinanceSkillsService
from rogueskills.application.case_artifact_builder import DigestRuntimeArtifactBuilder
from rogueskills.application.case_run_service import CaseRunService
from rogueskills.application.case_validation_service import CaseValidationService
from rogueskills.application.demo_finance_replay import DemoFinanceReplayService
from rogueskills.application.discovery_service import DiscoverySearchService
from rogueskills.application.errors import ApplicationError
from rogueskills.application.finance_artifact_builder import FinanceRuntimeArtifactBuilder
from rogueskills.application.finance_bootstrap import FinanceBootstrapService
from rogueskills.application.finance_case_service import FinanceCaseService
from rogueskills.application.multi_skill_preset_service import MultiSkillPresetService
from rogueskills.application.preset_service import AgentPresetService
from rogueskills.application.services import MaterialService, RunService, SkillService
from rogueskills.case_packs.finance import build_finance_case_pack
from rogueskills.case_packs.release import build_release_readiness_case_pack
from rogueskills.domain.benchmark import run_scenario_benchmark
from rogueskills.domain.case_pack import CasePackRegistry
from rogueskills.domain.catalogs import SEED_SKILLS, SOURCE_CONNECTORS
from rogueskills.domain.evolution import public_catalog
from rogueskills.domain.genome import capability_profile_from_genome, validate_skill_genome
from rogueskills.infrastructure.case_run_repository import CaseRunRepository
from rogueskills.infrastructure.case_store import CompatibleCaseRunStore
from rogueskills.infrastructure.case_validation_repository import CaseValidationRepository
from rogueskills.infrastructure.database import create_database
from rogueskills.infrastructure.finance_case_repository import FinanceCaseRepository
from rogueskills.infrastructure.preset_repository import AgentPresetRepository
from rogueskills.infrastructure.repository import SkillRepository
from rogueskills.settings import Settings

from .models import (
    AwesomeFinanceImportRequest,
    ChooseMutationRequest,
    CreateAgentPresetRequest,
    CreateCaseRunRequest,
    CreateCaseValidationRequest,
    CreateFinanceCaseRequest,
    CreateMultiSkillPresetRequest,
    CreateRunRequest,
    DiscoveryImportBatchRequest,
    DiscoverySearchRunRequest,
    FinanceBootstrapRequest,
    ImportRequest,
    MaterialConvertRequest,
    PromoteRequest,
    ReplayCaseRunRequest,
    RunRevisionRequest,
    SearchRequest,
    SelectNodeRequest,
    StartAutomaticRunRequest,
    StoreSkillRequest,
)


def create_app(
    config: Settings | None = None,
    *,
    http_client: httpx.AsyncClient | None = None,
    material_normalizer: MaterialNormalizer | None = None,
    finance_analyst: FinanceAnalyst | None = None,
    finance_data_gateway: SecFinanceDataGateway | None = None,
    release_data_gateway: GithubReleaseReadinessGateway | None = None,
) -> FastAPI:
    config = config or Settings()
    finance_analyst_injected = finance_analyst is not None
    engine, sessions = create_database(config.database_url)
    repository = SkillRepository(sessions)
    preset_repository = AgentPresetRepository(sessions)
    finance_case_repository = FinanceCaseRepository(sessions)
    case_run_repository = CaseRunRepository(sessions)
    case_validation_repository = CaseValidationRepository(sessions)
    case_store = CompatibleCaseRunStore(case_run_repository, finance_case_repository)
    skills = SkillService(repository)
    runs = RunService(repository)
    presets = AgentPresetService(repository, preset_repository)
    multi_skill_presets = MultiSkillPresetService(
        skills=repository,
        presets=preset_repository,
    )
    awesome_finance = AwesomeFinanceSkillsService(repository)
    demo_finance_replay = DemoFinanceReplayService(
        skills=repository,
        cases=case_run_repository,
    )
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=httpx.Timeout(config.search_provider_timeout_seconds),
        headers={"User-Agent": "RogueSkills-Discovery/0.3"},
    )
    gateway = DiscoveryGateway(
        client,
        github_token=config.github_token,
        brave_api_key=config.brave_api_key,
        tavily_api_key=config.tavily_api_key,
        exa_api_key=config.exa_api_key,
    )
    discovery = DiscoverySearchService(
        gateway,
        skills,
        max_results_per_provider=config.search_run_max_results_per_provider,
        max_provider_requests=config.search_run_max_provider_requests,
        retention_seconds=config.search_run_retention_seconds,
    )
    if material_normalizer is None:
        material_normalizer = (
            OpenAICompatibleMaterialNormalizer(
                client,
                base_url=config.llm_base_url,
                model=config.llm_model,
                api_key=config.llm_api_key,
                timeout_seconds=config.llm_timeout_seconds,
            )
            if config.llm_base_url and config.llm_model
            else UnavailableMaterialNormalizer()
        )
    materials = MaterialService(material_normalizer)
    finance = FinanceBootstrapService(
        gateway=gateway,
        materials=materials,
        skills=skills,
        repository=repository,
    )
    if finance_analyst is None:
        finance_analyst = (
            OpenAICompatibleFinanceAnalyst(
                client,
                base_url=config.llm_base_url,
                model=config.llm_model,
                api_key=config.llm_api_key,
                timeout_seconds=config.llm_timeout_seconds,
            )
            if config.llm_base_url and config.llm_model
            else UnavailableFinanceAnalyst()
        )
    resolved_finance_data_gateway = finance_data_gateway or SecFinanceDataGateway(
        client, sec_user_agent=config.sec_user_agent
    )
    case_pack_registry = CasePackRegistry()
    finance_artifact_builder = FinanceRuntimeArtifactBuilder(repository, presets)
    finance_case_pack = case_pack_registry.register(
        build_finance_case_pack(
            gateway=resolved_finance_data_gateway,
            analyst=finance_analyst,
            demo_analyst=None if finance_analyst_injected else DemoFinanceAnalyst(),
            artifact_builder=finance_artifact_builder,
        )
    )
    case_pack_registry.register(
        build_release_readiness_case_pack(
            gateway=release_data_gateway
            or GithubReleaseReadinessGateway(client, token=config.github_token),
            artifact_builder=DigestRuntimeArtifactBuilder(),
        )
    )
    case_runner = CaseRunService(
        skills=repository,
        cases=case_store,
        presets=preset_repository,
    )
    case_validations = CaseValidationService(
        skills=repository,
        presets=preset_repository,
        cases=case_store,
        validations=case_validation_repository,
    )
    finance_cases = FinanceCaseService(
        analyst=finance_analyst,
        skills=repository,
        case_pack=finance_case_pack,
        runner=case_runner,
    )
    search_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    automatic_run_tasks: dict[str, asyncio.Task[None]] = {}
    case_validation_tasks: dict[str, asyncio.Task[None]] = {}

    for seed in SEED_SKILLS:
        if not repository.get_skill(seed["id"]):
            repository.save_skill(seed, source_id="seed", trusted_status=True)

    # The checked-in Awesome Finance Skills snapshot is a local Demo fixture.
    # Seed it only for the normal local database so isolated tests and explicitly
    # configured databases retain the explicit import boundary.
    awesome_root = config.project_root / "Awesome-finance-skills"
    default_database_url = (
        f"sqlite:///{(config.project_root / 'data' / 'rogueskills.db').resolve()}"
    )
    demo_replay_seed: dict[str, Any] | None = None
    if config.database_url == default_database_url:
        if awesome_root.is_dir():
            awesome_finance.run(root=awesome_root, auto_promote=True)
        demo_replay_seed = demo_finance_replay.seed()

    def resolve_case_skill(
        *, skill_id: str, skill_version_id: str | None, auto_evolve: bool
    ) -> dict[str, Any]:
        skill = repository.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        if skill_version_id is None:
            return skill
        version = repository.get_skill_version(skill_version_id)
        if not version or version["skillId"] != skill_id:
            raise ApplicationError(
                "SKILL_VERSION_NOT_FOUND", "Skill Version 不存在或不属于该 Skill。", status_code=404
            )
        if version["genome"].get("status") != "initial":
            raise ApplicationError(
                "SKILL_VERSION_NOT_INITIAL",
                "只有历史上已进入 Initial 状态的 Skill Version 可以固定执行。",
                status_code=409,
            )
        if auto_evolve and skill["currentVersionId"] != skill_version_id:
            raise ApplicationError(
                "PINNED_SKILL_CANNOT_EVOLVE",
                "固定的历史 Skill Version 不能执行 autoEvolve；请使用当前版本。",
                status_code=409,
                details={"currentVersionId": skill["currentVersionId"]},
            )
        return {
            **skill,
            "currentVersionId": version["id"],
            "genome": version["genome"],
        }

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        tasks = [*automatic_run_tasks.values(), *case_validation_tasks.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await discovery.close()
        if owns_client:
            await client.aclose()
        engine.dispose()

    app = FastAPI(
        title="RogueSkills API",
        version="0.2.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = config
    app.state.repository = repository
    app.state.preset_repository = preset_repository
    app.state.finance_case_repository = finance_case_repository
    app.state.case_run_repository = case_run_repository
    app.state.case_validation_repository = case_validation_repository
    app.state.case_validation_service = case_validations
    app.state.demo_finance_replay_seed = demo_replay_seed
    app.state.case_store = case_store
    app.state.case_pack_registry = case_pack_registry

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid4().hex}"
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        try:
            declared_size = int(content_length) if content_length else 0
        except ValueError:
            declared_size = 0
        if declared_size > config.max_request_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": "请求体超过限制。",
                        "retryable": False,
                        "details": {},
                    },
                    "requestId": request_id,
                },
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ApplicationError)
    async def handle_application_error(request: Request, error: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "retryable": error.retryable,
                    "details": error.details,
                },
                "requestId": request.state.request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_FAILED",
                    "message": "请求参数不符合 API Contract。",
                    "retryable": False,
                    "details": {"errors": error.errors()},
                },
                "requestId": request.state.request_id,
            },
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        normalizer_info = materials.normalizer.info
        return {
            "status": "ok",
            "service": "rogueskills-api",
            "version": "0.2.0",
            "language": "python",
            "schemaVersion": "1.0.0",
            "materialNormalizer": {
                "mode": normalizer_info.mode,
                "provider": normalizer_info.provider,
                "model": normalizer_info.model,
                "configured": normalizer_info.configured,
            },
        }

    @app.get("/api/discovery/connectors")
    def discovery_connectors() -> dict[str, Any]:
        return {"connectors": SOURCE_CONNECTORS}

    @app.get("/api/discovery/providers")
    def discovery_providers() -> dict[str, Any]:
        return {"providers": discovery.providers()}

    @app.post("/api/discovery/search-runs", status_code=202)
    async def create_discovery_search_run(payload: DiscoverySearchRunRequest) -> dict[str, Any]:
        snapshot = discovery.create_run(
            query=payload.query.strip(),
            provider_ids=payload.providerIds,
            scope_ids=payload.scopeIds,
            include_local_examples=payload.includeLocalExamples,
        )
        return {
            **snapshot,
            "eventsUrl": f"/api/discovery/search-runs/{snapshot['run']['id']}/events",
        }

    @app.get("/api/discovery/search-runs/{run_id}")
    def get_discovery_search_run(run_id: str) -> dict[str, Any]:
        return discovery.snapshot(run_id)

    @app.get("/api/discovery/search-runs/{run_id}/events")
    async def stream_discovery_search_run(
        run_id: str,
        request: Request,
        after: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        last_event = request.headers.get("last-event-id")
        after_event_id = int(last_event) if last_event and last_event.isdigit() else after

        async def stream() -> AsyncIterator[str]:
            async for event in discovery.event_stream(run_id, after_event_id=after_event_id):
                if await request.is_disconnected():
                    return
                yield (
                    f"id: {event['eventId']}\n"
                    f"data: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
                )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/discovery/search-runs/{run_id}/cancel")
    async def cancel_discovery_search_run(run_id: str) -> dict[str, Any]:
        return await discovery.cancel(run_id)

    @app.get("/api/discovery/candidates/{candidate_id}/preview")
    def preview_discovery_candidate(candidate_id: str) -> dict[str, Any]:
        return discovery.preview(candidate_id)

    @app.post("/api/discovery/import-batches", status_code=201)
    async def import_discovery_batch(
        payload: DiscoveryImportBatchRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        return await discovery.import_candidates(
            run_id=payload.searchRunId,
            candidate_ids=payload.candidateIds,
            expected_revision=payload.expectedRunRevision,
            idempotency_key=idempotency_key or f"dib-key-{uuid4().hex}",
            acknowledged_warnings=[item.model_dump() for item in payload.acknowledgedWarnings],
        )

    @app.post("/api/discovery/search")
    async def search_discovery(payload: SearchRequest) -> dict[str, Any]:
        key = payload.model_dump_json()
        cached = search_cache.get(key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return {**cached[1], "cached": True}
        result = await gateway.federated_search(payload.query.strip(), source_ids=payload.sourceIds)
        search_cache[key] = (now + config.search_cache_ttl_seconds, result)
        return {**result, "cached": False}

    @app.post("/api/discovery/import", status_code=201)
    async def import_discovery(payload: ImportRequest) -> dict[str, Any]:
        imported = await gateway.ingest_candidate(payload.candidate)
        stored = skills.create_quarantine(
            imported["genome"],
            source_id=payload.candidate.get("sourceId", "discovery"),
            snapshot_content=imported["hydrated"].get("content"),
        )
        return {"skill": stored, "validation": validate_skill_genome(stored["genome"])}

    @app.post("/api/scenarios/finance/bootstrap")
    async def bootstrap_finance(payload: FinanceBootstrapRequest) -> dict[str, Any]:
        return await finance.run(
            max_community_skills=payload.maxCommunitySkills,
            sop_ids=payload.sopIds,
            auto_promote=payload.autoPromote,
        )

    @app.post("/api/scenarios/finance/import-awesome")
    def import_awesome_finance(payload: AwesomeFinanceImportRequest) -> dict[str, Any]:
        return awesome_finance.run(
            root=config.project_root / "Awesome-finance-skills",
            selected_names=payload.skillNames,
            auto_promote=payload.autoPromote,
        )

    @app.get("/api/finance/cases/preflight")
    def finance_case_preflight() -> dict[str, Any]:
        return finance_cases.preflight()

    @app.get("/api/case-packs")
    def list_case_packs() -> dict[str, Any]:
        return {"casePacks": case_pack_registry.descriptors()}

    @app.get("/api/case-packs/{case_pack_id}")
    def get_case_pack(case_pack_id: str, version: str | None = None) -> dict[str, Any]:
        try:
            pack = case_pack_registry.get(case_pack_id, version)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        return {
            "casePack": {
                **next(
                    item for item in case_pack_registry.descriptors() if item["ref"] == pack.ref
                ),
                "inputSchema": pack.input_model.model_json_schema()
                if pack.input_model is not None
                else None,
                "runtimePolicy": pack.runtime_policy.model_dump(mode="json"),
                "skillPolicy": pack.skill_policy.model_dump(mode="json"),
            }
        }

    @app.get("/api/case-runs/preflight")
    def generic_case_preflight(
        casePackId: str, casePackVersion: str | None = None
    ) -> dict[str, Any]:
        try:
            pack = case_pack_registry.get(casePackId, casePackVersion)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        return {
            "casePackId": pack.id,
            "casePackVersion": pack.version,
            **pack.preflight(),
        }

    @app.get("/api/case-runs")
    def list_case_runs(
        limit: int = Query(default=20, ge=1, le=100),
        casePackId: str | None = None,
    ) -> dict[str, Any]:
        return {"caseRuns": case_store.list(limit=limit, case_pack_id=casePackId)}

    @app.post("/api/case-runs", status_code=201)
    async def create_case_run(payload: CreateCaseRunRequest) -> dict[str, Any]:
        try:
            pack = case_pack_registry.get(payload.casePackId, payload.casePackVersion)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        skill = resolve_case_skill(
            skill_id=payload.skillId,
            skill_version_id=payload.skillVersionId,
            auto_evolve=payload.autoEvolve,
        )
        try:
            pack.validate_skill(skill)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_SKILL_INCOMPATIBLE",
                "Skill 不满足 Case Pack 的准入策略。",
                status_code=409,
            ) from error
        try:
            case_input = pack.validate_input(payload.input)
        except ValidationError as error:
            raise ApplicationError(
                "CASE_INPUT_INVALID",
                "Case Pack 输入不符合 Contract。",
                status_code=422,
                details={"errors": error.errors(include_url=False)},
            ) from error
        projected = pack.project_state(case_input)
        return {
            "caseRun": await case_runner.run(
                pack=pack,
                skill=skill,
                case_input=case_input,
                mode=payload.mode,
                replay_case_id=payload.replayCaseId,
                auto_evolve=payload.autoEvolve,
                run_id_prefix="case-run",
                initial_state_fields=projected,
            )
        }

    @app.get("/api/case-runs/{case_id}")
    def get_case_run(case_id: str) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("CASE_RUN_NOT_FOUND", "Case Run 不存在。", status_code=404)
        return {"caseRun": case}

    @app.get("/api/case-runs/{case_id}/report")
    def get_case_run_report(
        case_id: str,
        stage: str = Query(default="final", pattern="^(baseline|evolved|final)$"),
    ) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("CASE_RUN_NOT_FOUND", "Case Run 不存在。", status_code=404)
        report = (
            case.get("finalReport") if stage == "final" else (case.get(stage) or {}).get("report")
        )
        if not report:
            raise ApplicationError(
                "CASE_REPORT_NOT_AVAILABLE", "该阶段尚未生成报告。", status_code=409
            )
        return {"report": report}

    @app.get("/api/case-runs/{case_id}/evaluation")
    def get_case_run_evaluation(
        case_id: str,
        stage: str = Query(default="final", pattern="^(baseline|evolved|final)$"),
    ) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("CASE_RUN_NOT_FOUND", "Case Run 不存在。", status_code=404)
        evaluation = (
            case.get("finalEvaluation")
            if stage == "final"
            else (case.get(stage) or {}).get("evaluation")
        )
        if not evaluation:
            raise ApplicationError(
                "CASE_EVALUATION_NOT_AVAILABLE",
                "该阶段尚未生成 Evaluation。",
                status_code=409,
            )
        return {"evaluation": evaluation}

    @app.get("/api/case-runs/{case_id}/artifact")
    def get_case_run_artifact(case_id: str) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("CASE_RUN_NOT_FOUND", "Case Run 不存在。", status_code=404)
        artifact = case.get("runtimeArtifact") or case.get("agentPreset")
        if not artifact:
            raise ApplicationError(
                "CASE_ARTIFACT_NOT_AVAILABLE", "Case Run 尚未生成 Artifact。", status_code=409
            )
        return {"artifact": artifact}

    @app.post("/api/case-runs/{case_id}/replay", status_code=201)
    async def replay_case_run(case_id: str, payload: ReplayCaseRunRequest) -> dict[str, Any]:
        source = case_store.get(case_id)
        if not source:
            raise ApplicationError("CASE_RUN_NOT_FOUND", "Case Run 不存在。", status_code=404)
        try:
            pack = case_pack_registry.get(
                source.get("casePackId", "finance-stock-analysis"),
                source.get("casePackVersion"),
            )
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        skill = resolve_case_skill(
            skill_id=payload.skillId,
            skill_version_id=payload.skillVersionId,
            auto_evolve=payload.autoEvolve,
        )
        try:
            pack.validate_skill(skill)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_SKILL_INCOMPATIBLE",
                "Skill 不满足 Case Pack 的准入策略。",
                status_code=409,
            ) from error
        case_input = source.get("input") or {
            "ticker": source.get("ticker"),
            "asOfDate": source.get("asOfDate"),
        }
        return {
            "caseRun": await case_runner.run(
                pack=pack,
                skill=skill,
                case_input=case_input,
                mode="verified_replay",
                replay_case_id=case_id,
                auto_evolve=payload.autoEvolve,
                run_id_prefix="case-run",
                initial_state_fields=pack.project_state(case_input),
            )
        }

    @app.get("/api/finance/cases")
    def list_finance_cases(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        return {"cases": case_store.list(limit=limit, case_pack_id="finance-stock-analysis")}

    @app.post("/api/finance/cases", status_code=201)
    async def create_finance_case(payload: CreateFinanceCaseRequest) -> dict[str, Any]:
        return {
            "case": await finance_cases.run(
                ticker=payload.ticker,
                skill_id=payload.skillId,
                as_of_date=payload.asOfDate or datetime.now(UTC).date(),
                mode=payload.mode,
                replay_case_id=payload.replayCaseId,
                auto_evolve=payload.autoEvolve,
            )
        }

    @app.get("/api/finance/cases/{case_id}")
    def get_finance_case(case_id: str) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("FINANCE_CASE_NOT_FOUND", "金融 Case 不存在。", status_code=404)
        return {"case": case}

    @app.get("/api/finance/cases/{case_id}/report")
    def get_finance_case_report(
        case_id: str,
        stage: str = Query(default="final", pattern="^(baseline|evolved|final)$"),
    ) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("FINANCE_CASE_NOT_FOUND", "金融 Case 不存在。", status_code=404)
        report = (
            case.get("finalReport") if stage == "final" else (case.get(stage) or {}).get("report")
        )
        if not report:
            raise ApplicationError(
                "FINANCE_REPORT_NOT_AVAILABLE", "该阶段尚未生成报告。", status_code=409
            )
        return {"report": report}

    @app.get("/api/finance/cases/{case_id}/agent-preset")
    def get_finance_case_agent_preset(case_id: str) -> dict[str, Any]:
        case = case_store.get(case_id)
        if not case:
            raise ApplicationError("FINANCE_CASE_NOT_FOUND", "金融 Case 不存在。", status_code=404)
        preset = case.get("agentPreset")
        if not preset:
            raise ApplicationError(
                "FINANCE_CASE_PRESET_NOT_AVAILABLE",
                "真实 Case 尚未通过，不能生成 Runtime Verified AgentPreset。",
                status_code=409,
            )
        return {"preset": preset}

    @app.post("/api/materials/convert")
    async def convert_material(payload: MaterialConvertRequest) -> dict[str, Any]:
        genome, normalization = await materials.convert(
            title=payload.title,
            content=payload.content,
            source=payload.source,
            license_value=payload.license,
            kind=payload.kind,
        )
        return {
            "genome": genome,
            "validation": validate_skill_genome(genome),
            "normalization": normalization,
        }

    @app.get("/api/skills")
    def list_skills(status: str | None = Query(default=None)) -> dict[str, Any]:
        return {"skills": repository.list_skills(status=status)}

    @app.post("/api/skills", status_code=201)
    def store_skill(payload: StoreSkillRequest) -> dict[str, Any]:
        skill = skills.create_quarantine(
            payload.genome, source_id=payload.sourceId, snapshot_content=payload.snapshotContent
        )
        return {"skill": skill, "validation": validate_skill_genome(skill["genome"])}

    @app.get("/api/skills/{skill_id}")
    def get_skill(skill_id: str) -> dict[str, Any]:
        skill = repository.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        return {"skill": skill}

    @app.delete("/api/skills/{skill_id}")
    def delete_skill(skill_id: str) -> dict[str, bool]:
        if not repository.delete_skill(skill_id):
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        return {"deleted": True}

    @app.post("/api/skills/{skill_id}/benchmark")
    def benchmark_skill(skill_id: str) -> dict[str, Any]:
        evaluation, result = skills.benchmark(skill_id)
        return {"evaluation": evaluation, "result": result}

    @app.post("/api/skills/{skill_id}/promote")
    def promote_skill(skill_id: str, payload: PromoteRequest) -> dict[str, Any]:
        return {
            "skill": skills.promote(skill_id, payload.evaluationId, payload.expectedSkillVersionId)
        }

    @app.get("/api/skills/{skill_id}/evaluations")
    def skill_evaluations(skill_id: str) -> dict[str, Any]:
        skill = repository.get_skill(skill_id)
        if not skill:
            raise ApplicationError("SKILL_NOT_FOUND", "Skill 不存在。", status_code=404)
        return {"evaluations": skill["evaluations"]}

    @app.get("/api/library/initial")
    def initial_library() -> dict[str, Any]:
        library = repository.list_skills(status="initial")
        return {
            "skills": [
                {**skill, "capabilityProfile": capability_profile_from_genome(skill["genome"])}
                for skill in library
            ]
        }

    @app.get("/api/skill-versions/{version_id}")
    def get_skill_version(version_id: str) -> dict[str, Any]:
        version = repository.get_skill_version(version_id)
        if not version:
            raise ApplicationError(
                "SKILL_VERSION_NOT_FOUND", "Skill Version 不存在。", status_code=404
            )
        return {"version": version}

    @app.get("/api/evolution/catalog")
    def evolution_catalog() -> dict[str, Any]:
        return public_catalog()

    @app.post("/api/runs", status_code=201)
    def create_evolution_run(payload: CreateRunRequest) -> dict[str, Any]:
        return runs.create(seed=payload.seed, skill_id=payload.skillId, mode_id=payload.modeId)

    @app.get("/api/runs")
    def list_evolution_runs(
        limit: int = Query(default=20, ge=1, le=100),
        status: str | None = Query(default=None, min_length=1, max_length=32),
    ) -> dict[str, Any]:
        records = repository.list_runs(limit=limit, status=status)
        return {
            "runs": [
                {
                    **record,
                    "artifact": preset_repository.get_by_run_id(record["run"]["id"]),
                }
                for record in records
            ]
        }

    @app.get("/api/runs/{run_id}")
    async def get_evolution_run(run_id: str) -> dict[str, Any]:
        record = runs.get(run_id)
        if record["run"].get("automation", {}).get("status") == "running":
            ensure_automatic_run_task(run_id)
        return {
            **record,
            "artifact": preset_repository.get_by_run_id(run_id),
        }

    async def drive_case_validation(validation_id: str, pack: Any) -> None:
        try:
            await case_validations.execute(validation_id, pack=pack)
        except ApplicationError:
            return

    def ensure_case_validation_task(validation_id: str, pack: Any) -> None:
        current = case_validation_tasks.get(validation_id)
        if current and not current.done():
            return
        task = asyncio.create_task(drive_case_validation(validation_id, pack))
        case_validation_tasks[validation_id] = task

        def forget_case_validation(finished: asyncio.Task[None]) -> None:
            if case_validation_tasks.get(validation_id) is finished:
                case_validation_tasks.pop(validation_id, None)

        task.add_done_callback(forget_case_validation)

    @app.get("/api/runs/{run_id}/case-validation-options")
    def get_case_validation_options(
        run_id: str,
        casePackId: str = "finance-stock-analysis",
        casePackVersion: str | None = None,
        limit: int = Query(default=30, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            pack = case_pack_registry.get(casePackId, casePackVersion)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        return {"options": case_validations.options(run_id=run_id, pack=pack, limit=limit)}

    @app.get("/api/runs/{run_id}/case-validations")
    def list_run_case_validations(
        run_id: str, limit: int = Query(default=20, ge=1, le=100)
    ) -> dict[str, Any]:
        return {"validations": case_validations.list_for_run(run_id, limit=limit)}

    @app.post("/api/runs/{run_id}/case-validations", status_code=202)
    async def create_run_case_validation(
        run_id: str, payload: CreateCaseValidationRequest
    ) -> dict[str, Any]:
        try:
            pack = case_pack_registry.get(payload.casePackId, payload.casePackVersion)
        except ValueError as error:
            raise ApplicationError(
                "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
            ) from error
        state, created = case_validations.create(
            run_id=run_id,
            pack=pack,
            replay_case_id=payload.replayCaseId,
            case_input=payload.input,
            retry_failed=payload.retryFailed,
        )
        if state["status"] in {"queued", "running"}:
            ensure_case_validation_task(state["id"], pack)
        return {"validation": state, "created": created}

    @app.get("/api/case-validations/{validation_id}")
    def get_case_validation(validation_id: str) -> dict[str, Any]:
        state = case_validations.get(validation_id)
        if state["status"] in {"queued", "running"}:
            try:
                pack = case_pack_registry.get(state["casePackId"], state["casePackVersion"])
            except ValueError as error:
                raise ApplicationError(
                    "CASE_PACK_NOT_FOUND", "Case Pack 不存在。", status_code=404
                ) from error
            ensure_case_validation_task(validation_id, pack)
        return {"validation": state}

    @app.get("/api/demo/context")
    def get_demo_context() -> dict[str, Any]:
        """Expose the latest local Evolution demo as a read-only host context.

        This is intentionally separate from the mutation APIs.  A Codex MCP host
        can call it after the presenter finishes the browser flow and immediately
        answer questions about the selected Skill, accepted Mutations, Evolution
        milestones, and generated AgentPreset.
        """

        records = repository.list_runs(limit=20)
        if not records:
            return {
                "available": False,
                "message": "尚未创建 Evolution Run，请先在前端选择 Skill 并运行自进化。",
                "skill": None,
                "run": None,
                "artifact": None,
                "caseValidation": None,
                "promotion": None,
                "nodeHistorySummary": {},
                "demoScript": {},
                "catalog": {},
            }
        validation_candidates: list[dict[str, Any]] = []
        records_by_run_id = {
            str(item.get("run", {}).get("id")): item
            for item in records
            if isinstance(item.get("run"), dict) and item["run"].get("id")
        }
        for run_id in records_by_run_id:
            validation_candidates.extend(case_validations.list_for_run(run_id, limit=20))
        validation = (
            max(
                validation_candidates,
                key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")),
            )
            if validation_candidates
            else None
        )
        record = (
            records_by_run_id.get(str(validation.get("sourceRunId"))) if validation else None
        ) or records[0]
        run = record["run"]
        artifact = preset_repository.get_by_run_id(run["id"])
        catalog = public_catalog()
        mutation_ids = set(run.get("mutationIds", []))
        evolution_ids = set(run.get("evolutionIds", []))
        monster_ids = {
            item["monsterId"]
            for item in run.get("encounterHistory", [])
            if isinstance(item, dict) and item.get("monsterId")
        }
        context_run = {key: value for key, value in run.items() if key != "baseSkillGenome"}
        node_history = [item for item in run.get("nodeHistory", []) if isinstance(item, dict)]
        node_history_summary = {
            "saveVersion": run.get("saveVersion"),
            "total": len(node_history),
            "completed": sum(item.get("status") == "completed" for item in node_history),
            "failed": sum(item.get("status") == "failed" for item in node_history),
            "entered": sum(item.get("status") == "entered" for item in node_history),
            "legacyIncomplete": sum(bool(item.get("legacyIncomplete")) for item in node_history),
            "nodes": [
                {
                    "nodeId": item.get("nodeId"),
                    "sequence": item.get("sequence"),
                    "status": item.get("status"),
                    "type": item.get("type"),
                    "regionName": item.get("regionName"),
                    "selectedMutationId": (item.get("reward") or {}).get("selectedMutationId"),
                    "unlockedEvolutionIds": list(
                        (item.get("reward") or {}).get("unlockedEvolutionIds") or []
                    ),
                }
                for item in node_history
            ],
        }
        demo_script = {
            "title": "Awesome Finance Candidate 真实案例验证",
            "presentationOrder": [
                "先展示候选配置生成的公司研究报告与证据边界",
                "再对比基础技能版本与候选智能体预设的分数和硬门槛",
                "然后用节点历史解释候选配置如何形成",
                "最后说明运行时验证、验收和技能版本晋升是三个独立状态",
            ],
            "recommendedPrompt": (
                "生成最新 CaseValidation 的业务优先演示讲稿：先讲公司研究结论，"
                "再讲同源 A/B、节点历史、关联修复和晋升结果。"
            ),
            "attributionBoundary": "节点优化项与门槛修复是关联证据，不代表单项独立因果。",
        }
        return {
            "available": True,
            "message": "最新本地 Evolution Run 上下文。",
            "skill": repository.get_skill(run["baseSkillId"]),
            "run": {
                **record,
                "run": context_run,
            },
            "artifact": artifact,
            "caseValidation": validation,
            "promotion": (validation or {}).get("promotion") if validation else None,
            "nodeHistorySummary": node_history_summary,
            "demoScript": demo_script,
            "catalog": {
                "mutations": [item for item in catalog["mutations"] if item["id"] in mutation_ids],
                "evolutions": [
                    item for item in catalog["evolutions"] if item["id"] in evolution_ids
                ],
                "monsters": {
                    monster_id: catalog["monsters"][monster_id]
                    for monster_id in monster_ids
                    if monster_id in catalog["monsters"]
                },
                "statLabels": catalog["statLabels"],
                "runMode": catalog["runModes"].get(run.get("modeId")),
            },
        }

    @app.post("/api/runs/{run_id}/select-node")
    def select_evolution_node(run_id: str, payload: SelectNodeRequest) -> dict[str, Any]:
        return runs.select_node(run_id, payload.nodeId, payload.expectedRevision)

    @app.post("/api/runs/{run_id}/resolve")
    def resolve_evolution_node(run_id: str, payload: RunRevisionRequest) -> dict[str, Any]:
        return runs.resolve(run_id, payload.expectedRevision)

    @app.post("/api/runs/{run_id}/choose-mutation")
    def choose_evolution_mutation(run_id: str, payload: ChooseMutationRequest) -> dict[str, Any]:
        return runs.choose_mutation(run_id, payload.mutationId, payload.expectedRevision)

    @app.post("/api/runs/{run_id}/skip-mutation")
    def skip_evolution_mutation(run_id: str, payload: RunRevisionRequest) -> dict[str, Any]:
        return runs.skip_mutation(run_id, payload.expectedRevision)

    async def drive_automatic_run(run_id: str) -> None:
        while True:
            await asyncio.sleep(config.automatic_run_step_delay_seconds)
            record = runs.get(run_id)
            automation = record["run"].get("automation") or {}
            if automation.get("status") != "running":
                return
            record = runs.advance_automatic(run_id, record["revision"])
            automation = record["run"].get("automation") or {}
            if automation.get("status") == "running":
                continue
            if record["run"]["status"] == "victory":
                project = automation["project"]
                presets.create(
                    run_id=run_id,
                    expected_revision=record["revision"],
                    project_name=project["name"],
                    project_description=project["description"],
                    scenario=project["scenario"],
                )
            return

    def ensure_automatic_run_task(run_id: str) -> None:
        current = automatic_run_tasks.get(run_id)
        if current and not current.done():
            return
        task = asyncio.create_task(drive_automatic_run(run_id))
        automatic_run_tasks[run_id] = task

        def forget_automatic_run(finished: asyncio.Task[None]) -> None:
            if automatic_run_tasks.get(run_id) is finished:
                automatic_run_tasks.pop(run_id, None)

        task.add_done_callback(forget_automatic_run)

    @app.post("/api/runs/{run_id}/auto")
    async def start_automatic_evolution(
        run_id: str, payload: StartAutomaticRunRequest
    ) -> dict[str, Any]:
        record = runs.start_automatic(
            run_id,
            selected_monster_ids=payload.selectedMonsterIds,
            project={
                "name": payload.projectName,
                "description": payload.projectDescription,
                "scenario": payload.scenario,
            },
            revision=payload.expectedRevision,
        )
        ensure_automatic_run_task(run_id)
        return {**record, "artifact": None}

    @app.post("/api/runs/{run_id}/agent-preset", status_code=201)
    def create_agent_preset(run_id: str, payload: CreateAgentPresetRequest) -> dict[str, Any]:
        preset, created = presets.create(
            run_id=run_id,
            expected_revision=payload.expectedRevision,
            project_name=payload.projectName,
            project_description=payload.projectDescription,
            scenario=payload.scenario,
        )
        return {"preset": preset, "created": created}

    @app.post("/api/multi-skill-presets", status_code=201)
    def create_multi_skill_preset(
        payload: CreateMultiSkillPresetRequest,
    ) -> dict[str, Any]:
        merge_run, preset, created = multi_skill_presets.create(
            primary_run_id=payload.primaryRunId,
            primary_role=payload.primaryRole,
            supporting_runs=[item.model_dump(mode="json") for item in payload.supportingRuns],
            routing=[item.model_dump(mode="json") for item in payload.routing],
            project_name=payload.projectName,
            project_description=payload.projectDescription,
            scenario=payload.scenario,
        )
        return {"mergeRun": merge_run, "preset": preset, "created": created}

    @app.get("/api/agent-presets")
    def list_agent_presets() -> dict[str, Any]:
        return {"presets": preset_repository.list()}

    @app.get("/api/agent-presets/{preset_id}")
    def get_agent_preset(preset_id: str) -> dict[str, Any]:
        return {"preset": presets.get(preset_id)}

    @app.get("/api/agent-presets/{preset_id}/export")
    def export_agent_preset(preset_id: str) -> JSONResponse:
        preset = presets.get(preset_id)
        return JSONResponse(
            content=preset,
            headers={
                "Content-Disposition": f'attachment; filename="{preset_id}.json"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/agent-presets/{preset_id}/export/{target}")
    def export_agent_preset_package(preset_id: str, target: AgentPresetExportTarget) -> Response:
        try:
            artifact = build_agent_preset_export(presets.get(preset_id), target)
        except AgentPresetIntegrityError as error:
            raise ApplicationError(
                "AGENT_PRESET_INTEGRITY_FAILED",
                "AgentPreset 内容校验失败。",
                status_code=409,
            ) from error
        return Response(
            content=artifact.content,
            media_type=artifact.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/agent-presets/{preset_id}/runtime-config")
    def agent_preset_runtime_config(preset_id: str) -> dict[str, Any]:
        try:
            runtime_config = load_agent_preset(presets.get(preset_id))
        except AgentPresetIntegrityError as error:
            raise ApplicationError(
                "AGENT_PRESET_INTEGRITY_FAILED",
                "AgentPreset 内容校验失败。",
                status_code=409,
            ) from error
        return {"runtimeConfig": runtime_config}

    @app.post("/api/benchmark/scenario")
    def scenario_preview(payload: dict[str, Any]) -> dict[str, Any]:
        result = run_scenario_benchmark(
            profile=payload["profile"],
            scenario=payload["scenario"],
            difficulty=payload["difficulty"],
            node_type=payload.get("nodeType", "normal"),
            compute_available=payload.get("computeAvailable", 100),
            objective_score=payload.get("objectiveScore", 0),
        )
        return {
            "result": result,
            "authoritative": False,
            "warning": "该接口仅用于预览；权威结果由 /api/runs 状态机生成。",
        }

    root = config.project_root

    def schema_file() -> FileResponse:
        path = root / "src" / "contracts" / "skill-genome.schema.json"
        if not path.is_file():
            raise ApplicationError("FILE_NOT_FOUND", "文件不存在。", status_code=404)
        return FileResponse(
            path, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        )

    @app.get("/api/schemas/skill-genome.schema.json", include_in_schema=False)
    def genome_schema() -> FileResponse:
        return schema_file()

    @app.get("/schemas/skill-genome.schema.json", include_in_schema=False)
    def genome_schema_compatibility() -> FileResponse:
        return schema_file()

    return app
