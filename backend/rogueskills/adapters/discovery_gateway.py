import asyncio
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from rogueskills.adapters.safe_web_fetcher import SafeWebFetcher
from rogueskills.adapters.web_search import WebSearchGateway, WebSearchProviderError
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
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        github_token: str | None = None,
        brave_api_key: str | None = None,
        tavily_api_key: str | None = None,
        exa_api_key: str | None = None,
    ) -> None:
        self.client = client
        self.github_token = github_token
        self.web_search = WebSearchGateway(
            client,
            brave_api_key=brave_api_key,
            tavily_api_key=tavily_api_key,
            exa_api_key=exa_api_key,
        )
        self.web_fetcher = SafeWebFetcher(client)

    def provider_catalog(self) -> list[dict[str, Any]]:
        definitions = [
            {
                "id": "github",
                "name": "GitHub Search API",
                "shortName": "GH",
                "description": "搜索公开仓库和 SKILL.md，并固定 Commit 快照。",
                "capabilities": ["code_search", "repository_search", "raw_content"],
                "configured": bool(self.github_token),
            },
            {
                "id": "brave",
                "name": "Brave Search API",
                "shortName": "BRV",
                "description": "搜索全网公开 Skill、文档和 Registry 页面。",
                "capabilities": ["web_search"],
                "configured": self.web_search.configured("brave"),
            },
            {
                "id": "tavily",
                "name": "Tavily Search API",
                "shortName": "TVL",
                "description": "补充研究型和长尾 Skill 来源。",
                "capabilities": ["web_search", "research_search"],
                "configured": self.web_search.configured("tavily"),
            },
            {
                "id": "exa",
                "name": "Exa Search API",
                "shortName": "EXA",
                "description": "使用语义搜索召回能力相近的 Skill 页面。",
                "capabilities": ["web_search", "semantic_search"],
                "configured": self.web_search.configured("exa"),
            },
        ]
        return [
            {
                **definition,
                "available": definition["configured"],
                "state": "ready" if definition["configured"] else "not_configured",
            }
            for definition in definitions
        ]

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

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlsplit(url.strip())
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}{path}"

    async def search_provider_sources(
        self, provider_id: str, query: str, *, limit: int = 8
    ) -> list[dict[str, Any]]:
        """Search one real provider and return origin-level hits."""
        if provider_id == "github":
            if not self.github_token:
                raise WebSearchProviderError("github", "NOT_CONFIGURED", "GitHub Token 尚未配置")
            return await self._search_github_sources(query, limit=limit)
        hits = await self.web_search.search(provider_id, query, limit=limit)
        return [
            {
                "kind": "web_page",
                "title": hit["title"],
                "url": hit["url"],
                "canonicalUrl": self._canonical_url(hit["url"]),
                "publisher": urlsplit(hit["url"]).hostname or "unknown",
                "snippet": hit["snippet"],
                "providerId": provider_id,
                "providerRank": hit["rank"],
                "providerScore": hit.get("providerScore"),
                "providerExtractedContent": hit.get("providerExtractedContent"),
                "metadata": {},
            }
            for hit in hits
        ]

    async def _search_github_sources(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        parsed = parse_search_query(query)
        terms = parsed["text"] or "agent skill workflow"
        exact = self._parse_repository_reference(terms)
        headers = self._headers(
            "https://api.github.com/", accept="application/vnd.github+json"
        )
        if exact:
            url = f"https://api.github.com/repos/{exact}"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            repositories = [response.json()]
            code_items: list[dict[str, Any]] = []
        else:
            code_url = "https://api.github.com/search/code"
            repo_url = "https://api.github.com/search/repositories"
            code_response, repo_response = await asyncio.gather(
                self.client.get(
                    code_url,
                    params={"q": f"{terms} filename:SKILL.md", "per_page": limit},
                    headers=headers,
                ),
                self.client.get(
                    repo_url,
                    params={
                        "q": f"{terms} skill in:name,description,readme",
                        "sort": "updated",
                        "order": "desc",
                        "per_page": limit,
                    },
                    headers=headers,
                ),
            )
            if code_response.status_code in (403, 429) or repo_response.status_code in (403, 429):
                raise WebSearchProviderError("github", "RATE_LIMITED", "GitHub API 已达到速率限制")
            # Code Search can reject broad queries. Repository Search still provides a useful path.
            code_items = (
                code_response.json().get("items", []) if code_response.status_code == 200 else []
            )
            repo_response.raise_for_status()
            repositories = repo_response.json().get("items", [])

        sources: list[dict[str, Any]] = []
        for rank, item in enumerate(code_items[:limit], start=1):
            repository = item.get("repository") or {}
            full_name = repository.get("full_name")
            if not full_name or not item.get("html_url"):
                continue
            sources.append(
                {
                    "kind": "github_file",
                    "title": f"{full_name}/{item.get('path', item.get('name', 'SKILL.md'))}",
                    "url": item["html_url"],
                    "canonicalUrl": self._canonical_url(item["html_url"]),
                    "publisher": (repository.get("owner") or {}).get("login")
                    or full_name.split("/")[0],
                    "snippet": f"GitHub Code Search 命中 {item.get('path', 'SKILL.md')}",
                    "providerId": "github",
                    "providerRank": rank,
                    "metadata": {
                        "apiUrl": item.get("url"),
                        "fullName": full_name,
                        "path": item.get("path"),
                        "sha": item.get("sha"),
                        "repositoryApiUrl": repository.get("url"),
                    },
                }
            )
        for rank, item in enumerate(repositories[:limit], start=1):
            if not item.get("html_url") or not item.get("full_name"):
                continue
            sources.append(
                {
                    "kind": "github_repository",
                    "title": item["full_name"],
                    "url": item["html_url"],
                    "canonicalUrl": self._canonical_url(item["html_url"]),
                    "publisher": (item.get("owner") or {}).get("login")
                    or item["full_name"].split("/")[0],
                    "snippet": item.get("description") or "GitHub 公开仓库",
                    "providerId": "github",
                    "providerRank": rank,
                    "metadata": {
                        "fullName": item["full_name"],
                        "defaultBranch": item.get("default_branch") or "main",
                        "license": (item.get("license") or {}).get("spdx_id", "unknown"),
                        "updatedAt": item.get("updated_at"),
                        "stars": item.get("stargazers_count", 0),
                        "topics": item.get("topics", []),
                    },
                }
            )
        unique: dict[str, dict[str, Any]] = {}
        for source in sources:
            unique.setdefault(source["canonicalUrl"], source)
        return list(unique.values())

    @staticmethod
    def _artifact_candidate(
        source: dict[str, Any],
        *,
        content: str,
        artifact_path: str,
        url: str,
        revision: str | None,
        license_value: str,
    ) -> dict[str, Any]:
        metadata = source.get("metadata", {})
        name = source["title"] if artifact_path == "WEB_PAGE" else artifact_path
        return {
            "name": name,
            "summary": source.get("snippet") or content[:280],
            "kind": "skill"
            if re.search(r"(?:^|/)skill\.md$|\bskill\b", f"{artifact_path} {content[:500]}", re.I)
            else "material",
            "sourceId": "github" if source["kind"].startswith("github_") else "web",
            "platform": "GitHub"
            if source["kind"].startswith("github_")
            else (urlsplit(url).hostname or "Web"),
            "author": source.get("publisher") or "Unknown",
            "license": license_value,
            "updatedAt": metadata.get("updatedAt"),
            "tags": list(dict.fromkeys([*metadata.get("topics", []), "web-discovery"]))[:12],
            "url": url,
            "content": content,
            "signals": {
                "official": False,
                "completeness": 72 if len(content) > 600 else 50,
                "stars": metadata.get("stars", 0),
            },
            "snapshot": {
                "status": "captured",
                "fingerprint": content_fingerprint(content),
                "artifactPaths": [artifact_path],
                "revision": revision,
                "fetchedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
        }

    async def materialize_source(
        self, source: dict[str, Any], *, max_artifacts: int = 8
    ) -> list[dict[str, Any]]:
        """Read origin content and enumerate concrete skill artifacts."""
        kind = source["kind"]
        metadata = source.get("metadata", {})
        if kind == "github_file":
            api_url = metadata.get("apiUrl")
            if not api_url:
                return []
            response = await self.client.get(
                api_url,
                headers=self._headers(api_url, accept="application/vnd.github.raw+json"),
            )
            response.raise_for_status()
            path = metadata.get("path") or "SKILL.md"
            return [
                self._artifact_candidate(
                    source,
                    content=response.text[:120_000],
                    artifact_path=path,
                    url=source["url"],
                    revision=metadata.get("sha"),
                    license_value="unknown",
                )
            ]
        if kind == "github_repository":
            full_name = metadata["fullName"]
            branch = metadata.get("defaultBranch") or "main"
            commit_url = f"https://api.github.com/repos/{full_name}/commits/{quote(branch, safe='')}"
            commit_response = await self.client.get(
                commit_url,
                headers=self._headers(commit_url, accept="application/vnd.github+json"),
            )
            commit_response.raise_for_status()
            revision = commit_response.json()["sha"]
            tree_url = f"https://api.github.com/repos/{full_name}/git/trees/{revision}?recursive=1"
            tree_response = await self.client.get(
                tree_url,
                headers=self._headers(tree_url, accept="application/vnd.github+json"),
            )
            tree_response.raise_for_status()
            paths = sorted(
                [
                    item["path"]
                    for item in tree_response.json().get("tree", [])
                    if item.get("type") == "blob"
                    and re.search(r"(^|/)skill\.md$", item.get("path", ""), re.I)
                ],
                key=lambda value: (len(value.split("/")), value),
            )[:max_artifacts]
            if not paths:
                readme_url = f"https://api.github.com/repos/{full_name}/readme?ref={revision}"
                response = await self.client.get(
                    readme_url,
                    headers=self._headers(readme_url, accept="application/vnd.github.raw+json"),
                )
                response.raise_for_status()
                paths = ["README"]
                contents = [response.text[:120_000]]
            else:
                responses = await asyncio.gather(
                    *[
                        self.client.get(
                            f"https://raw.githubusercontent.com/{full_name}/{revision}/{quote(path, safe='/')}",
                            headers={"Accept": "text/plain"},
                        )
                        for path in paths
                    ]
                )
                for response in responses:
                    response.raise_for_status()
                contents = [response.text[:120_000] for response in responses]
            return [
                self._artifact_candidate(
                    source,
                    content=content,
                    artifact_path=path,
                    url=(
                        source["url"]
                        if path == "README"
                        else f"https://github.com/{full_name}/blob/{revision}/{path}"
                    ),
                    revision=revision,
                    license_value=metadata.get("license", "unknown"),
                )
                for path, content in zip(paths, contents, strict=True)
            ]
        fetched = await self.web_fetcher.fetch(source["url"])
        content = fetched["content"]
        if not content:
            return []
        return [
            self._artifact_candidate(
                source,
                content=content,
                artifact_path="WEB_PAGE",
                url=fetched["finalUrl"],
                revision=content_fingerprint(content),
                license_value="unknown",
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
        if candidate.get("content") and candidate.get("snapshot", {}).get("status") == "captured":
            return candidate
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
