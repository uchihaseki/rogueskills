# RogueSkills Python Architecture v0.2

## 1. Architecture decision

RogueSkills adopts a modular monolith for P1:

```text
Browser ES Modules
       │ REST / SSE
       ▼
FastAPI Transport
       │
Application Commands ───────────────┐
       │                            │
       ▼                            ▼
Pure Python Domain             Background Queue
       │                            │
       ▼                            ▼
SQLAlchemy Repository          LangGraph Runtime
       │                            │
       ▼                            ▼
SQLite / PostgreSQL       LLM / Playwright / MCP Adapters
```

The project must not split into independent network services until runtime workers have demonstrated an independent scaling or security requirement. Package boundaries are enforced now so a worker can be extracted later without moving domain rules.

## 2. Dependency direction

```text
api → application → domain
api → adapters / infrastructure
agents → contracts + ports
adapters → domain contracts
infrastructure → domain data
domain → Python standard library only
frontend → HTTP API only
```

The domain package cannot import FastAPI, SQLAlchemy, LangGraph, network clients, environment variables, databases or browser APIs.

## 3. Framework decisions

| Concern | Decision | Reason |
|---|---|---|
| HTTP and OpenAPI | FastAPI + Pydantic v2 | Typed contracts, generated OpenAPI and async adapter support |
| Domain algorithms | Pure Python | Deterministic tests and no framework coupling |
| Persistence | SQLAlchemy 2 + Alembic | SQLite migration compatibility and PostgreSQL production path |
| Agent orchestration | LangGraph | Explicit, checkpointable graph with branching and human approval points |
| Background work | Celery + Redis | Queueing, retries, timeout and cancellation for P1 executions |
| Browser runtime | Playwright Python Adapter | Deterministic tool boundary and isolated execution |
| LLM providers | `ModelProvider`/`RuntimeAdapter` ports | Avoid provider SDK types in domain/application code |
| Observability | OpenTelemetry + Langfuse | Correlated request, execution, trace, token and latency data |
| Frontend | ES Modules during migration; React/TypeScript only when component complexity requires it | Keeps the existing UI while removing client authority first |

CrewAI, AutoGen and PydanticAI are not used alongside LangGraph. Multiple orchestration frameworks would duplicate state, retry and tracing semantics.

## 4. Agent boundary

Only nondeterministic proposal or tool-execution work is modeled as an Agent:

1. Normalizer Agent: untrusted material → `NormalizedMaterial` JSON Contract；正式材料 API 不再使用正则抽取。
2. Runtime Agent: immutable Genome + Runtime Case → output and sanitized trace.
3. Mutation Planner: evaluation evidence → three whitelist JSON Patch proposals.

The following remain deterministic services:

- JSON Schema and static safety validation
- license gates
- metric calculation and score aggregation
- Hidden Test access policy
- lifecycle transitions
- version creation and candidate promotion

An LLM may propose a transition input, but it can never perform the transition itself.

## 5. Authoritative Evolution flow

```text
POST /api/runs
  → validate Initial Skill and immutable version
  → create server Run state, revision 1

select-node(expectedRevision)
  → server validates current phase
  → revision + 1

resolve(expectedRevision)
  → Python Benchmark/Evaluator
  → persist result and next state atomically
  → revision + 1

choose-mutation(expectedRevision)
  → validate proposal and complexity budget
  → apply server-side effects
  → revision + 1
```

Stale commands return `STALE_RUN_REVISION`. The browser persists only the Run reference and last displayed summary; reloading retrieves the canonical state from the API.

## 6. Lifecycle invariants

- Generic create/update forces `quarantine`.
- Published/Initial skills cannot be changed through the generic save command.
- Admission Evaluation is bound to `skill_version_id`.
- Promotion validates `expectedSkillVersionId` and rejects stale Evaluation.
- Version JSON is immutable; a change creates a child version.
- Candidate creation will require a successful Hidden Evaluation tied to the current evolving version.

## 7. Data placement

| Data | Storage |
|---|---|
| Skill identity and lifecycle | PostgreSQL relational columns |
| Immutable Genome versions | PostgreSQL JSON/JSONB payload plus lineage columns |
| Source snapshots | Object storage for large content; PostgreSQL metadata |
| Runtime traces | S3/MinIO, with sanitized index in PostgreSQL |
| Queue and short-lived locks | Redis |
| Search text | PostgreSQL FTS/`pg_trgm` initially |
| Embeddings | pgvector only after a measured retrieval requirement |
| Hidden datasets | backend-only object prefix and dedicated access policy |

SQLite remains supported for local development and migration tests.

## 8. Runtime graph

The initial LangGraph extension point in `backend/rogueskills/agents/evolution_graph.py` has three nodes:

```text
execute_runtime → evaluate_output ──passed──→ end
                           └────failed──────→ propose_mutations → end
```

Human selection, JSON Patch application, Validation and Hidden Boss will be added as explicit nodes. Durable queue state remains owned by the worker/application layer; domain functions remain replayable without LangGraph.

## 9. Migration status

Completed in v0.2:

- Python Genome, Discovery, Benchmark and Evolution algorithms
- frozen Python-owned JSON catalogs and seed data
- JS/Python parity checks for deterministic behavior
- FastAPI API and same-origin frontend serving
- SQLAlchemy Repository and initial Alembic baseline
- lifecycle and stale Evaluation protections
- server-authoritative Run state with optimistic revision
- API-only frontend paths
- frozen Node implementation moved to `legacy/`
- typed Runtime/Evaluation/Mutation contracts and LangGraph ports

Still to implement:

- Celery task execution and cancellation endpoints
- real LLM and Playwright Runtime Adapters
- execution/trace/object-storage tables
- Dataset Pack and Hidden split authorization
- whitelist Genome Patch application and Candidate persistence
- React/TypeScript component migration if the UI outgrows current modules

## 10. Delivery gates

Every new Runtime or Agent change must include:

1. versioned request/result contract;
2. deterministic fixture adapter;
3. timeout and cancellation behavior;
4. sanitized trace test;
5. retry classification;
6. Golden evaluation regression;
7. proof that Hidden input and answer are absent from browser and Mutation context.
