import asyncio
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from rogueskills.domain.catalogs import SOURCE_CONNECTORS
from rogueskills.domain.discovery import (
    candidate_to_skill_genome,
    content_fingerprint,
    deduplicate_candidates,
    matches_filters,
    parse_search_query,
    rank_candidate,
    search_local_index,
)


class DiscoveryGateway:
    def __init__(self, client: httpx.AsyncClient, *, github_token: str | None = None) -> None:
        self.client = client
        self.github_token = github_token

    def _headers(self, url: str, *, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        if self.github_token and url.startswith("https://api.github.com/"):
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    @staticmethod
    def _infer_kind(item: dict[str, Any]) -> str:
        text = f"{item.get('name', '')} {item.get('description', '')} {' '.join(item.get('topics', []))}".lower()
        if re.search(r"\b(skill|agent skill|prompt)\b", text):
            return "skill"
        if re.search(r"\b(sop|runbook|playbook|procedure)\b", text):
            return "sop"
        if re.search(r"\bchecklist\b", text):
            return "checklist"
        return "material"

    @classmethod
    def _github_candidate(cls, item: dict[str, Any], connector: dict[str, Any]) -> dict[str, Any]:
        full_name = item["full_name"]
        license_value = (item.get("license") or {}).get("spdx_id", "unknown")
        return {
            "id": f"{connector['id']}-{item['id']}",
            "name": full_name,
            "summary": item.get("description") or "公开 GitHub 仓库，等待拉取内容快照。",
            "kind": cls._infer_kind(item),
            "sourceId": connector["id"],
            "platform": connector["name"],
            "author": (item.get("owner") or {}).get("login") or full_name.split("/")[0],
            "license": license_value,
            "updatedAt": item.get("updated_at"),
            "tags": list(dict.fromkeys([*item.get("topics", []), "github"]))[:12],
            "url": item.get("html_url"),
            "fullName": full_name,
            "defaultBranch": item.get("default_branch"),
            "content": item.get("description") or "",
            "signals": {
                "official": bool(connector.get("official")),
                "completeness": 58 if item.get("description") else 35,
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
            },
            "snapshot": {"status": "metadata_only", "fingerprint": None, "artifactPaths": []},
        }

    @staticmethod
    def _parse_repository_reference(value: str) -> str | None:
        text = value.strip()
        match = re.match(r"^https?://github\.com/([^/\s]+)/([^/#?\s]+)(?:[/?#].*)?$", text, re.I)
        if match:
            return f"{match.group(1)}/{re.sub(r'\.git$', '', match.group(2), flags=re.I)}"
        short = re.match(r"^([\w.-]+)/([\w.-]+)$", text)
        return (
            f"{short.group(1)}/{re.sub(r'\.git$', '', short.group(2), flags=re.I)}"
            if short
            else None
        )

    async def search_github(
        self, query: str, connector: dict[str, Any], *, limit: int = 12
    ) -> list[dict[str, Any]]:
        parsed = parse_search_query(query)
        terms = parsed["text"] or "agent skill workflow"
        exact = self._parse_repository_reference(terms) if connector["id"] == "github" else None
        if exact:
            url = f"https://api.github.com/repos/{exact}"
            response = await self.client.get(
                url, headers=self._headers(url, accept="application/vnd.github+json")
            )
            response.raise_for_status()
            return [rank_candidate(self._github_candidate(response.json(), connector), query)]
        skill_hint = (
            "" if re.search(r"(?:skill|sop|runbook|workflow|agent)", terms, re.I) else " skill"
        )
        qualifier = f" {connector['qualifier']}" if connector.get("qualifier") else ""
        search = f"{terms}{skill_hint} in:name,description,readme{qualifier}".strip()
        url = "https://api.github.com/search/repositories"
        response = await self.client.get(
            url,
            params={"q": search, "sort": "updated", "order": "desc", "per_page": limit},
            headers=self._headers(url, accept="application/vnd.github+json"),
        )
        if response.status_code in (403, 429):
            raise RuntimeError("GitHub 公共 API 已达到速率限制")
        response.raise_for_status()
        return [
            candidate
            for item in response.json().get("items", [])
            if matches_filters(
                (candidate := rank_candidate(self._github_candidate(item, connector), query)),
                parsed["filters"],
            )
        ]

    async def federated_search(
        self, query: str, *, source_ids: list[str] | None = None, limit_per_source: int = 12
    ) -> dict[str, Any]:
        source_ids = source_ids or ["builtin", "github"]
        connectors = [
            connector
            for connector_id in source_ids
            for connector in SOURCE_CONNECTORS
            if connector["id"] == connector_id
        ]

        async def search(connector: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            if connector["mode"] == "local":
                results = search_local_index(query)
                return results, {"sourceId": connector["id"], "state": "ok", "count": len(results)}
            if connector["mode"] != "github":
                return [], {"sourceId": connector["id"], "state": "unavailable", "count": 0}
            try:
                results = await self.search_github(query, connector, limit=limit_per_source)
                return results, {"sourceId": connector["id"], "state": "ok", "count": len(results)}
            except (httpx.HTTPError, RuntimeError) as error:
                return [], {
                    "sourceId": connector["id"],
                    "state": "error",
                    "count": 0,
                    "message": str(error),
                }

        responses = await asyncio.gather(*(search(connector) for connector in connectors))
        collected = [candidate for results, _status in responses for candidate in results]
        status = [status for _results, status in responses]
        results = sorted(
            deduplicate_candidates(collected),
            key=lambda candidate: candidate["ranking"]["total"],
            reverse=True,
        )
        return {"results": results, "status": status}

    async def _fetch_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.text

    async def hydrate_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate = deepcopy(candidate)
        if not candidate.get("fullName"):
            content = candidate.get("content") or candidate.get("summary") or ""
            candidate["snapshot"] = {
                "status": "captured" if content else "metadata_only",
                "fingerprint": content_fingerprint(content),
                "artifactPaths": [],
            }
            return candidate
        branch = candidate.get("defaultBranch") or "main"
        tree_url = f"https://api.github.com/repos/{candidate['fullName']}/git/trees/{quote(branch, safe='')}?recursive=1"
        try:
            tree_response = await self.client.get(
                tree_url, headers=self._headers(tree_url, accept="application/vnd.github+json")
            )
            tree_response.raise_for_status()
            skill_paths = sorted(
                (
                    item["path"]
                    for item in tree_response.json().get("tree", [])
                    if item.get("type") == "blob"
                    and re.search(r"(^|/)skill\.md$", item.get("path", ""), re.I)
                ),
                key=lambda path: len(path.split("/")),
            )[:1]
            if skill_paths:
                contents = await asyncio.gather(
                    *(
                        self._fetch_text(
                            f"https://raw.githubusercontent.com/{candidate['fullName']}/{branch}/{path}"
                        )
                        for path in skill_paths
                    )
                )
                artifact_paths = skill_paths
            else:
                contents = [
                    await self._fetch_text(
                        f"https://api.github.com/repos/{candidate['fullName']}/readme",
                        headers={"Accept": "application/vnd.github.raw+json"},
                    )
                ]
                artifact_paths = ["README"]
            content = "\n\n---\n\n".join(contents)[:120_000]
            candidate["content"] = content
            candidate["snapshot"] = {
                "status": "captured",
                "fingerprint": content_fingerprint(content),
                "artifactPaths": artifact_paths,
                "revision": branch,
                "fetchedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        except httpx.HTTPError as error:
            content = candidate.get("content") or candidate.get("summary") or ""
            candidate["snapshot"] = {
                "status": "metadata_only",
                "fingerprint": content_fingerprint(content),
                "artifactPaths": [],
                "error": str(error),
            }
        return candidate

    async def ingest_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        hydrated = await self.hydrate_candidate(candidate)
        return {"genome": candidate_to_skill_genome(hydrated), "hydrated": hydrated}
