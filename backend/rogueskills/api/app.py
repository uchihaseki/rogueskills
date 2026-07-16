from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from rogueskills.adapters.discovery_gateway import DiscoveryGateway
from rogueskills.adapters.llm_material_normalizer import OpenAICompatibleMaterialNormalizer
from rogueskills.agents.material_normalizer import MaterialNormalizer, UnavailableMaterialNormalizer
from rogueskills.application.errors import ApplicationError
from rogueskills.application.services import MaterialService, RunService, SkillService
from rogueskills.domain.benchmark import run_scenario_benchmark
from rogueskills.domain.catalogs import SEED_SKILLS, SOURCE_CONNECTORS
from rogueskills.domain.evolution import public_catalog
from rogueskills.domain.genome import capability_profile_from_genome, validate_skill_genome
from rogueskills.infrastructure.database import create_database
from rogueskills.infrastructure.repository import SkillRepository
from rogueskills.settings import Settings

from .models import (
    ChooseMutationRequest,
    CreateRunRequest,
    ImportRequest,
    MaterialConvertRequest,
    PromoteRequest,
    RunRevisionRequest,
    SearchRequest,
    SelectNodeRequest,
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
    skills = SkillService(repository)
    runs = RunService(repository)
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
    search_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    for seed in SEED_SKILLS:
        if not repository.get_skill(seed["id"]):
            repository.save_skill(seed, source_id="seed", trusted_status=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
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
    app.state.settings = config
    app.state.repository = repository

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
    def get_evolution_run(run_id: str) -> dict[str, Any]:
        return runs.get(run_id)

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

    def static_file(path: Path) -> FileResponse:
        if not path.is_file():
            raise ApplicationError("FILE_NOT_FOUND", "文件不存在。", status_code=404)
        return FileResponse(
            path, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return static_file(root / "index.html")

    @app.get("/index.html", include_in_schema=False)
    def index_compatibility() -> FileResponse:
        return static_file(root / "index.html")

    @app.get("/discovery.html", include_in_schema=False)
    def discovery_page() -> FileResponse:
        return static_file(root / "discovery.html")

    @app.get("/{asset_name:str}", include_in_schema=False)
    def root_asset(asset_name: str) -> FileResponse:
        if asset_name not in {"styles.css", "discovery.css"}:
            raise ApplicationError("FILE_NOT_FOUND", "文件不存在。", status_code=404)
        return static_file(root / asset_name)

    @app.get("/src/frontend/{asset_path:path}", include_in_schema=False)
    def frontend_asset(asset_path: str) -> FileResponse:
        base = (root / "src" / "frontend").resolve()
        path = (base / asset_path).resolve()
        if base not in path.parents or path.suffix != ".js":
            raise ApplicationError("FILE_NOT_FOUND", "文件不存在。", status_code=404)
        return static_file(path)

    @app.get("/schemas/skill-genome.schema.json", include_in_schema=False)
    def genome_schema() -> FileResponse:
        return static_file(root / "src" / "contracts" / "skill-genome.schema.json")

    return app
