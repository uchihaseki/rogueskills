from __future__ import annotations

from typing import Any

import httpx


class WebSearchProviderError(RuntimeError):
    def __init__(self, provider_id: str, code: str, message: str) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.code = code


class WebSearchGateway:
    """Small adapters around official JSON search APIs.

    These adapters only discover URLs. Fetching and trusting the origin content remains
    RogueSkills' responsibility.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        brave_api_key: str | None = None,
        tavily_api_key: str | None = None,
        exa_api_key: str | None = None,
    ) -> None:
        self.client = client
        self.keys = {
            "brave": brave_api_key,
            "tavily": tavily_api_key,
            "exa": exa_api_key,
        }

    def configured(self, provider_id: str) -> bool:
        return bool(self.keys.get(provider_id))

    @staticmethod
    def _raise_for_provider(response: httpx.Response, provider_id: str) -> None:
        if response.status_code in (401, 403):
            raise WebSearchProviderError(provider_id, "AUTH_FAILED", "搜索 API 鉴权失败")
        if response.status_code == 429:
            raise WebSearchProviderError(provider_id, "RATE_LIMITED", "搜索 API 已达到速率限制")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise WebSearchProviderError(
                provider_id,
                "UPSTREAM_ERROR",
                f"搜索 API 返回 HTTP {response.status_code}",
            ) from error

    @staticmethod
    def _hit(
        *,
        provider_id: str,
        url: str,
        title: str,
        snippet: str,
        rank: int,
        provider_score: float | None = None,
        extracted_content: str | None = None,
    ) -> dict[str, Any]:
        return {
            "providerId": provider_id,
            "url": url,
            "title": title or url,
            "snippet": snippet,
            "rank": rank,
            "providerScore": provider_score,
            "providerExtractedContent": extracted_content,
        }

    async def search(self, provider_id: str, query: str, *, limit: int) -> list[dict[str, Any]]:
        if not self.configured(provider_id):
            raise WebSearchProviderError(provider_id, "NOT_CONFIGURED", "搜索 API 尚未配置")
        if provider_id == "brave":
            return await self._search_brave(query, limit=limit)
        if provider_id == "tavily":
            return await self._search_tavily(query, limit=limit)
        if provider_id == "exa":
            return await self._search_exa(query, limit=limit)
        raise WebSearchProviderError(provider_id, "UNKNOWN_PROVIDER", "未知搜索 Provider")

    async def _search_brave(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        provider_id = "brave"
        response = await self.client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit, "safesearch": "moderate"},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": str(self.keys[provider_id]),
            },
        )
        self._raise_for_provider(response, provider_id)
        items = (response.json().get("web") or {}).get("results", [])
        return [
            self._hit(
                provider_id=provider_id,
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                snippet=str(item.get("description") or ""),
                rank=index + 1,
            )
            for index, item in enumerate(items[:limit])
            if item.get("url")
        ]

    async def _search_tavily(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        provider_id = "tavily"
        response = await self.client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.keys[provider_id],
                "query": query,
                "search_depth": "advanced",
                "max_results": limit,
                "include_raw_content": False,
            },
            headers={"Accept": "application/json"},
        )
        self._raise_for_provider(response, provider_id)
        return [
            self._hit(
                provider_id=provider_id,
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                snippet=str(item.get("content") or ""),
                rank=index + 1,
                provider_score=float(item["score"]) if item.get("score") is not None else None,
            )
            for index, item in enumerate(response.json().get("results", [])[:limit])
            if item.get("url")
        ]

    async def _search_exa(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        provider_id = "exa"
        response = await self.client.post(
            "https://api.exa.ai/search",
            json={
                "query": query,
                "type": "auto",
                "numResults": limit,
                "contents": {"text": {"maxCharacters": 1200}},
            },
            headers={
                "Accept": "application/json",
                "x-api-key": str(self.keys[provider_id]),
            },
        )
        self._raise_for_provider(response, provider_id)
        return [
            self._hit(
                provider_id=provider_id,
                url=str(item.get("url") or ""),
                title=str(item.get("title") or ""),
                snippet=str(item.get("text") or "")[:1200],
                rank=index + 1,
                provider_score=float(item["score"]) if item.get("score") is not None else None,
                extracted_content=str(item.get("text") or "") or None,
            )
            for index, item in enumerate(response.json().get("results", [])[:limit])
            if item.get("url")
        ]
