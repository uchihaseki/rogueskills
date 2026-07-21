from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from rogueskills.adapters.discovery_gateway import DiscoveryGateway
from rogueskills.adapters.web_search import WebSearchProviderError
from rogueskills.application.errors import ApplicationError
from rogueskills.domain.discovery import candidate_to_skill_genome, rank_candidate

TERMINAL_STATES = {"review_ready", "failed", "cancelled", "expired"}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class DiscoverySearchService:
    """In-process Search Run orchestrator.

    Search state is intentionally server-owned so previews and imports can reference immutable
    candidate IDs instead of trusting candidate objects returned by the browser.
    """

    def __init__(
        self,
        gateway: DiscoveryGateway,
        skills: Any,
        *,
        max_results_per_provider: int = 8,
        max_provider_requests: int = 16,
        retention_seconds: int = 86_400,
    ) -> None:
        self.gateway = gateway
        self.skills = skills
        self.max_results_per_provider = max_results_per_provider
        self.max_provider_requests = max_provider_requests
        self.retention_seconds = retention_seconds
        self.records: dict[str, dict[str, Any]] = {}
        self.import_batches: dict[str, dict[str, Any]] = {}

    def providers(self) -> list[dict[str, Any]]:
        return self.gateway.provider_catalog()

    @staticmethod
    def _query_plan(query: str) -> list[dict[str, str]]:
        normalized = " ".join(query.split())
        plans = [{"id": "qry_01", "text": normalized, "intent": "user_query"}]
        if "skill" not in normalized.casefold() and "SKILL.md" not in normalized:
            plans.append(
                {
                    "id": "qry_02",
                    "text": f"{normalized} agent skill SKILL.md",
                    "intent": "exact_skill",
                }
            )
        return plans

    def create_run(
        self,
        *,
        query: str,
        provider_ids: list[str],
        scope_ids: list[str],
        include_local_examples: bool,
    ) -> dict[str, Any]:
        self._expire_old_runs()
        known = {provider["id"] for provider in self.providers()}
        invalid = sorted(set(provider_ids) - known)
        if invalid:
            raise ApplicationError(
                "UNKNOWN_SEARCH_PROVIDER",
                "包含未知 Search Provider。",
                status_code=422,
                details={"providerIds": invalid},
            )
        run_id = f"dsr_{uuid4().hex}"
        created_at = datetime.now(UTC)
        selected_provider_ids = list(dict.fromkeys(provider_ids))
        run = {
            "id": run_id,
            "query": query,
            "state": "queued",
            "providerIds": selected_provider_ids,
            "scopeIds": scope_ids,
            "includeLocalExamples": include_local_examples,
            "revision": 1,
            "policyVersion": "discovery-selection-v1",
            "counts": {
                "sourceHits": 0,
                "artifacts": 0,
                "candidates": 0,
                "recommended": 0,
                "blocked": 0,
            },
            "createdAt": created_at.isoformat().replace("+00:00", "Z"),
            "expiresAt": (created_at + timedelta(seconds=self.retention_seconds))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        record: dict[str, Any] = {
            "run": run,
            "queries": [],
            "providerStatus": {
                provider_id: {"providerId": provider_id, "state": "queued", "count": 0}
                for provider_id in selected_provider_ids
            },
            "sources": {},
            "sourceKeys": {},
            "candidates": {},
            "candidateKeys": {},
            "events": [],
            "condition": asyncio.Condition(),
            "task": None,
        }
        self.records[run_id] = record
        record["task"] = asyncio.create_task(self._execute(run_id))
        return self.snapshot(run_id)

    async def _emit(self, record: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        run = record["run"]
        run["revision"] += 1
        event = {
            "eventId": len(record["events"]) + 1,
            "runId": run["id"],
            "revision": run["revision"],
            "timestamp": _now(),
            "type": event_type,
            "payload": payload,
        }
        record["events"].append(event)
        async with record["condition"]:
            record["condition"].notify_all()

    async def _set_provider_status(
        self,
        record: dict[str, Any],
        provider_id: str,
        *,
        state: str,
        count: int = 0,
        code: str | None = None,
        message: str | None = None,
    ) -> None:
        status = {
            "providerId": provider_id,
            "state": state,
            "count": count,
            "code": code,
            "message": message,
        }
        record["providerStatus"][provider_id] = status
        await self._emit(record, f"provider.{state}", status)

    async def _execute(self, run_id: str) -> None:
        record = self.records[run_id]
        run = record["run"]
        try:
            run["state"] = "planning"
            await self._emit(record, "run.created", {"run": deepcopy(run)})
            query_budget = max(
                1,
                self.max_provider_requests // max(1, len(run["providerIds"])),
            )
            queries = self._query_plan(run["query"])[:query_budget]
            record["queries"] = queries
            await self._emit(record, "query.planned", {"queries": queries})
            run["state"] = "searching"
            provider_catalog = {provider["id"]: provider for provider in self.providers()}

            async def search_provider(provider_id: str) -> None:
                provider = provider_catalog[provider_id]
                if not provider["configured"]:
                    await self._set_provider_status(
                        record,
                        provider_id,
                        state="skipped",
                        code="NOT_CONFIGURED",
                        message="API Key 尚未配置",
                    )
                    return
                await self._set_provider_status(record, provider_id, state="started")
                found = 0
                try:
                    for query in queries:
                        hits = await self.gateway.search_provider_sources(
                            provider_id,
                            query["text"],
                            limit=self.max_results_per_provider,
                        )
                        for hit in hits:
                            added = await self._upsert_source(record, hit, query_id=query["id"])
                            found += int(added)
                    await self._set_provider_status(
                        record, provider_id, state="completed", count=found
                    )
                except WebSearchProviderError as error:
                    state = "rate_limited" if error.code == "RATE_LIMITED" else "error"
                    await self._set_provider_status(
                        record,
                        provider_id,
                        state=state,
                        count=found,
                        code=error.code,
                        message=str(error),
                    )
                except (httpx.HTTPError, ValueError) as error:
                    await self._set_provider_status(
                        record,
                        provider_id,
                        state="error",
                        count=found,
                        code="UPSTREAM_ERROR",
                        message=str(error),
                    )

            await asyncio.gather(*(search_provider(provider_id) for provider_id in run["providerIds"]))
            successful = [
                status
                for status in record["providerStatus"].values()
                if status["state"] == "completed"
            ]
            if not successful:
                run["state"] = "failed"
                await self._emit(
                    record,
                    "run.failed",
                    {"code": "NO_REMOTE_PROVIDER_SUCCEEDED", "run": deepcopy(run)},
                )
                return

            run["state"] = "hydrating"
            semaphore = asyncio.Semaphore(5)

            async def hydrate(source: dict[str, Any]) -> None:
                async with semaphore:
                    try:
                        artifacts = await self.gateway.materialize_source(source)
                        for artifact in artifacts:
                            await self._add_candidate(record, source, artifact)
                    except (httpx.HTTPError, ValueError, KeyError) as error:
                        source["status"] = "content_unavailable"
                        source["error"] = str(error)
                        await self._emit(
                            record,
                            "source.failed",
                            {"sourceId": source["id"], "message": str(error)},
                        )

            await asyncio.gather(*(hydrate(source) for source in list(record["sources"].values())))
            run["state"] = "filtering"
            self._apply_recommendations(record)
            run["counts"] = {
                "sourceHits": len(record["sources"]),
                "artifacts": len(record["candidates"]),
                "candidates": len(record["candidates"]),
                "recommended": sum(
                    1
                    for candidate in record["candidates"].values()
                    if candidate["selection"]["recommended"]
                ),
                "blocked": sum(
                    1
                    for candidate in record["candidates"].values()
                    if not candidate["selection"]["eligible"]
                ),
            }
            run["state"] = "review_ready"
            await self._emit(
                record,
                "run.review_ready",
                {"run": deepcopy(run), "recommendedIds": self.recommended_ids(run_id)},
            )
        except asyncio.CancelledError:
            run["state"] = "cancelled"
            await self._emit(record, "run.cancelled", {"run": deepcopy(run)})
            raise
        except Exception as error:
            run["state"] = "failed"
            await self._emit(
                record,
                "run.failed",
                {"code": "SEARCH_RUN_FAILED", "message": str(error), "run": deepcopy(run)},
            )

    async def _upsert_source(
        self, record: dict[str, Any], hit: dict[str, Any], *, query_id: str
    ) -> bool:
        key = hit["canonicalUrl"]
        discovery = {
            "providerId": hit["providerId"],
            "queryId": query_id,
            "rank": hit.get("providerRank"),
            "snippet": hit.get("snippet"),
        }
        existing_id = record["sourceKeys"].get(key)
        if existing_id:
            source = record["sources"][existing_id]
            if hit["kind"].startswith("github_") and source["kind"] == "web_page":
                preserved = source["discoveredBy"]
                source.update(deepcopy(hit))
                source["id"] = existing_id
                source["discoveredBy"] = preserved
                source["status"] = "found"
            marker = (discovery["providerId"], discovery["queryId"])
            known = {(item["providerId"], item["queryId"]) for item in source["discoveredBy"]}
            if marker not in known:
                source["discoveredBy"].append(discovery)
                await self._emit(record, "source.updated", {"source": self._public_source(source)})
            return False
        source_id = f"src_{uuid4().hex}"
        source = {
            **deepcopy(hit),
            "id": source_id,
            "status": "found",
            "discoveredAt": _now(),
            "discoveredBy": [discovery],
        }
        record["sourceKeys"][key] = source_id
        record["sources"][source_id] = source
        record["run"]["counts"]["sourceHits"] = len(record["sources"])
        await self._emit(record, "source.found", {"source": self._public_source(source)})
        return True

    async def _add_candidate(
        self, record: dict[str, Any], source: dict[str, Any], artifact: dict[str, Any]
    ) -> None:
        artifact_path = (artifact.get("snapshot") or {}).get("artifactPaths", ["SOURCE"])[0]
        ranked = rank_candidate(artifact, record["run"]["query"])
        risk_level = ranked.get("risk", {}).get("level", "medium")
        eligible = risk_level != "high" and ranked.get("snapshot", {}).get("status") == "captured"
        fingerprint = ranked.get("snapshot", {}).get("fingerprint")
        key = str(fingerprint or f"{artifact.get('url')}|{artifact_path}")
        existing_id = record["candidateKeys"].get(key)
        if existing_id:
            existing = record["candidates"][existing_id]
            discoveries = [*existing["discoveredBy"], *source["discoveredBy"]]
            unique_discoveries = {
                (item["providerId"], item["queryId"]): item for item in discoveries
            }
            source_hit_ids = list(
                dict.fromkeys([*existing.get("sourceHitIds", []), source["id"]])
            )
            prefer_new = (
                ranked["ranking"]["total"] > existing["ranking"]["total"]
                or (
                    existing.get("license") in {None, "", "unknown", "NOASSERTION"}
                    and ranked.get("license") not in {None, "", "unknown", "NOASSERTION"}
                )
            )
            if prefer_new:
                replacement = {
                    **ranked,
                    "id": existing_id,
                    "sourceHitId": source["id"],
                    "sourceHitIds": source_hit_ids,
                    "artifactPath": artifact_path,
                    "discoveredBy": list(unique_discoveries.values()),
                    "selection": {
                        "eligible": eligible,
                        "recommended": False,
                        "reasonCodes": []
                        if eligible
                        else ["HIGH_RISK_OR_CONTENT_UNAVAILABLE"],
                    },
                    "previewState": "ready",
                }
                record["candidates"][existing_id] = replacement
                existing = replacement
            else:
                existing["discoveredBy"] = list(unique_discoveries.values())
                existing["sourceHitIds"] = source_hit_ids
            source["status"] = "enumerated"
            source.setdefault("artifactIds", []).append(existing_id)
            await self._emit(
                record,
                "candidate.updated",
                {"candidate": self._public_candidate(existing)},
            )
            return
        candidate_id = f"cand_{uuid4().hex}"
        candidate = {
            **ranked,
            "id": candidate_id,
            "sourceHitId": source["id"],
            "sourceHitIds": [source["id"]],
            "artifactPath": artifact_path,
            "discoveredBy": deepcopy(source["discoveredBy"]),
            "selection": {
                "eligible": eligible,
                "recommended": False,
                "reasonCodes": [] if eligible else ["HIGH_RISK_OR_CONTENT_UNAVAILABLE"],
            },
            "previewState": "ready",
        }
        record["candidateKeys"][key] = candidate_id
        record["candidates"][candidate_id] = candidate
        source["status"] = "enumerated"
        source.setdefault("artifactIds", []).append(candidate_id)
        record["run"]["counts"]["artifacts"] = len(record["candidates"])
        record["run"]["counts"]["candidates"] = len(record["candidates"])
        await self._emit(
            record,
            "artifact.found",
            {
                "sourceId": source["id"],
                "candidate": self._public_candidate(candidate),
            },
        )
        await self._emit(
            record, "candidate.scored", {"candidate": self._public_candidate(candidate)}
        )

    @staticmethod
    def _apply_recommendations(record: dict[str, Any]) -> None:
        candidates = sorted(
            record["candidates"].values(),
            key=lambda candidate: candidate["ranking"]["total"],
            reverse=True,
        )
        selected = 0
        source_counts: dict[str, int] = {}
        for candidate in candidates:
            selection = candidate["selection"]
            license_value = str(candidate.get("license") or "unknown")
            risk_level = candidate.get("risk", {}).get("level")
            source_id = candidate["sourceHitId"]
            allowed_license = license_value not in {"unknown", "NOASSERTION", ""}
            can_recommend = (
                selection["eligible"]
                and risk_level == "low"
                and allowed_license
                and candidate["ranking"]["total"] >= 58
                and selected < 5
                and source_counts.get(source_id, 0) < 2
            )
            selection["recommended"] = can_recommend
            if can_recommend:
                selection["reasonCodes"] = [
                    "HIGH_RELEVANCE",
                    "CAPTURED_ORIGIN",
                    "LICENSE_ALLOWED",
                ]
                selected += 1
                source_counts[source_id] = source_counts.get(source_id, 0) + 1
            elif selection["eligible"] and not selection["reasonCodes"]:
                selection["reasonCodes"] = [
                    "LICENSE_REVIEW_REQUIRED" if not allowed_license else "BELOW_RECOMMENDATION_CUTOFF"
                ]

    @staticmethod
    def _public_source(source: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(value)
            for key, value in source.items()
            if key not in {"metadata", "providerExtractedContent"}
        }

    @staticmethod
    def _public_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(value)
            for key, value in candidate.items()
            if key not in {"content", "fullName", "defaultBranch"}
        }

    def snapshot(self, run_id: str) -> dict[str, Any]:
        record = self._record(run_id)
        return {
            "run": deepcopy(record["run"]),
            "queries": deepcopy(record["queries"]),
            "providerStatus": list(deepcopy(record["providerStatus"]).values()),
            "sources": [self._public_source(source) for source in record["sources"].values()],
            "candidates": [
                self._public_candidate(candidate)
                for candidate in sorted(
                    record["candidates"].values(),
                    key=lambda item: item["ranking"]["total"],
                    reverse=True,
                )
            ],
        }

    def recommended_ids(self, run_id: str) -> list[str]:
        record = self._record(run_id)
        return [
            candidate_id
            for candidate_id, candidate in record["candidates"].items()
            if candidate["selection"]["recommended"]
        ]

    def preview(self, candidate_id: str) -> dict[str, Any]:
        _record, candidate = self._candidate(candidate_id)
        genome = candidate_to_skill_genome(candidate)
        return {
            "candidate": self._public_candidate(candidate),
            "rawContent": candidate.get("content", "")[:120_000],
            "genome": genome,
            "source": self._public_source(_record["sources"][candidate["sourceHitId"]]),
        }

    async def import_candidates(
        self,
        *,
        run_id: str,
        candidate_ids: list[str],
        expected_revision: int,
        idempotency_key: str,
        acknowledged_warnings: list[dict[str, str]],
    ) -> dict[str, Any]:
        if idempotency_key in self.import_batches:
            return deepcopy(self.import_batches[idempotency_key])
        record = self._record(run_id)
        if record["run"]["state"] != "review_ready":
            raise ApplicationError(
                "SEARCH_RUN_NOT_READY", "Search Run 尚未进入人工复核状态。", status_code=409
            )
        if record["run"]["revision"] != expected_revision:
            raise ApplicationError(
                "STALE_SEARCH_RUN",
                "搜索结果已经变化，请刷新后重新确认。",
                status_code=409,
                details={"currentRevision": record["run"]["revision"]},
            )
        unique_ids = list(dict.fromkeys(candidate_ids))
        if not unique_ids:
            raise ApplicationError("EMPTY_IMPORT_SELECTION", "至少选择一个候选。", status_code=422)
        unknown = [candidate_id for candidate_id in unique_ids if candidate_id not in record["candidates"]]
        if unknown:
            raise ApplicationError(
                "CANDIDATE_NOT_IN_SEARCH_RUN",
                "候选不属于当前 Search Run。",
                status_code=422,
                details={"candidateIds": unknown},
            )
        acknowledged = {
            (item.get("candidateId"), item.get("code")) for item in acknowledged_warnings
        }
        items: list[dict[str, Any]] = []
        await self._emit(record, "import.started", {"candidateIds": unique_ids})
        for candidate_id in unique_ids:
            candidate = record["candidates"][candidate_id]
            if not candidate["selection"]["eligible"]:
                items.append(
                    {
                        "candidateId": candidate_id,
                        "state": "rejected",
                        "reasonCode": "CANDIDATE_BLOCKED",
                    }
                )
                continue
            warning = next(
                (
                    code
                    for code in candidate["selection"]["reasonCodes"]
                    if code in {"LICENSE_REVIEW_REQUIRED"}
                ),
                None,
            )
            if warning and (candidate_id, warning) not in acknowledged:
                items.append(
                    {
                        "candidateId": candidate_id,
                        "state": "rejected",
                        "reasonCode": warning,
                    }
                )
                continue
            try:
                imported = await self.gateway.ingest_candidate(candidate)
                stored = self.skills.create_quarantine(
                    imported["genome"],
                    source_id=candidate.get("sourceId", "discovery"),
                    snapshot_content=imported["hydrated"].get("content"),
                )
                item = {
                    "candidateId": candidate_id,
                    "state": "saved",
                    "skillId": stored["id"],
                }
            except (ApplicationError, httpx.HTTPError, ValueError) as error:
                item = {
                    "candidateId": candidate_id,
                    "state": "failed",
                    "reasonCode": getattr(error, "code", "IMPORT_FAILED"),
                    "message": str(error),
                }
            items.append(item)
            await self._emit(record, "import.item_completed", {"item": item})
        summary = {
            state: sum(1 for item in items if item["state"] == state)
            for state in ("saved", "existing", "rejected", "failed")
        }
        batch = {
            "batchId": f"dib_{uuid4().hex}",
            "searchRunId": run_id,
            "summary": summary,
            "items": items,
            "createdAt": _now(),
        }
        self.import_batches[idempotency_key] = deepcopy(batch)
        await self._emit(record, "import.completed", {"batch": batch})
        return batch

    async def event_stream(
        self, run_id: str, *, after_event_id: int = 0
    ) -> AsyncIterator[dict[str, Any]]:
        record = self._record(run_id)
        cursor = max(0, after_event_id)
        while True:
            events = record["events"]
            while cursor < len(events):
                event = events[cursor]
                cursor += 1
                yield deepcopy(event)
            if record["run"]["state"] in TERMINAL_STATES:
                return
            async with record["condition"]:
                try:
                    await asyncio.wait_for(record["condition"].wait(), timeout=15)
                except TimeoutError:
                    yield {
                        "eventId": cursor,
                        "runId": run_id,
                        "revision": record["run"]["revision"],
                        "timestamp": _now(),
                        "type": "heartbeat",
                        "payload": {},
                    }

    async def cancel(self, run_id: str) -> dict[str, Any]:
        record = self._record(run_id)
        task = record.get("task")
        if task and not task.done():
            task.cancel()
        return self.snapshot(run_id)

    async def close(self) -> None:
        tasks = [record.get("task") for record in self.records.values()]
        active = [task for task in tasks if task and not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    def _record(self, run_id: str) -> dict[str, Any]:
        record = self.records.get(run_id)
        if not record:
            raise ApplicationError("SEARCH_RUN_NOT_FOUND", "Search Run 不存在。", status_code=404)
        return record

    def _candidate(self, candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for record in self.records.values():
            if candidate_id in record["candidates"]:
                return record, record["candidates"][candidate_id]
        raise ApplicationError("DISCOVERY_CANDIDATE_NOT_FOUND", "候选不存在。", status_code=404)

    def _expire_old_runs(self) -> None:
        now = datetime.now(UTC)
        for record in self.records.values():
            expires = datetime.fromisoformat(record["run"]["expiresAt"].replace("Z", "+00:00"))
            if expires <= now and record["run"]["state"] not in {"expired", "cancelled"}:
                record["run"]["state"] = "expired"
