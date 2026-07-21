from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from rogueskills.adapters.agent_preset_exporter import (
    AgentPresetExportTarget,
    build_agent_preset_export,
)
from rogueskills.adapters.agent_preset_loader import (
    AgentPresetIntegrityError,
    load_agent_preset,
)
from rogueskills.adapters.discovery_gateway import DiscoveryGateway
from rogueskills.adapters.llm_material_normalizer import OpenAICompatibleMaterialNormalizer
from rogueskills.agents.material_normalizer import MaterialNormalizer, UnavailableMaterialNormalizer
from rogueskills.application.errors import ApplicationError
from rogueskills.application.finance_bootstrap import FinanceBootstrapService
from rogueskills.application.preset_service import AgentPresetService
from rogueskills.application.services import MaterialService, RunService, SkillService
from rogueskills.domain.benchmark import run_scenario_benchmark
from rogueskills.domain.catalogs import SEED_SKILLS, SOURCE_CONNECTORS
from rogueskills.domain.evolution import public_catalog
from rogueskills.domain.genome import capability_profile_from_genome, validate_skill_genome
from rogueskills.infrastructure.database import create_database
from rogueskills.infrastructure.preset_repository import AgentPresetRepository
from rogueskills.infrastructure.repository import SkillRepository
from rogueskills.settings import Settings

from .models import (
    ChooseMutationRequest,
    CreateAgentPresetRequest,
    CreateRunRequest,
    FinanceBootstrapRequest,
    ImportRequest,
    MaterialConvertRequest,
    PromoteRequest,
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
) -> FastAPI:
    config = config or Settings()
    engine, sessions = create_database(config.database_url)
    repository = SkillRepository(sessions)
    preset_repository = AgentPresetRepository(sessions)
    skills = SkillService(repository)
    runs = RunService(repository)
    presets = AgentPresetService(repository, preset_repository)
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=httpx.Timeout(20), headers={"User-Agent": "RogueSkills-Discovery/0.2"}
    )
    gateway = DiscoveryGateway(client, github_token=config.github_token)
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
    search_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    automatic_run_tasks: dict[str, asyncio.Task[None]] = {}

    for seed in SEED_SKILLS:
        if not repository.get_skill(seed["id"]):
            repository.save_skill(seed, source_id="seed", trusted_status=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        tasks = list(automatic_run_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
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

    @app.get("/api/evolution/catalog")
    def evolution_catalog() -> dict[str, Any]:
        return public_catalog()

    @app.post("/api/runs", status_code=201)
    def create_evolution_run(payload: CreateRunRequest) -> dict[str, Any]:
        return runs.create(seed=payload.seed, skill_id=payload.skillId, mode_id=payload.modeId)

    @app.get("/api/runs/{run_id}")
    async def get_evolution_run(run_id: str) -> dict[str, Any]:
        record = runs.get(run_id)
        if record["run"].get("automation", {}).get("status") == "running":
            ensure_automatic_run_task(run_id)
        return {
            **record,
            "artifact": preset_repository.get_by_run_id(run_id),
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
    def create_agent_preset(
        run_id: str, payload: CreateAgentPresetRequest
    ) -> dict[str, Any]:
        preset, created = presets.create(
            run_id=run_id,
            expected_revision=payload.expectedRevision,
            project_name=payload.projectName,
            project_description=payload.projectDescription,
            scenario=payload.scenario,
        )
        return {"preset": preset, "created": created}

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
    def export_agent_preset_package(
        preset_id: str, target: AgentPresetExportTarget
    ) -> Response:
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
