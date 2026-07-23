from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from rogueskills.application.errors import ApplicationError
from rogueskills.contracts.case_runtime import CaseSourcePolicy


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _fetched_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class GithubReleaseReadinessGateway:
    API_ROOT = "https://api.github.com"

    def __init__(self, client: httpx.AsyncClient, *, token: str | None = None) -> None:
        self.client = client
        self.token = token
        self.calls = 0

    async def _get(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> httpx.Response:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RogueSkills-Release-Readiness/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        url = f"{self.API_ROOT}{path}"
        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as error:
            raise ApplicationError(
                "RELEASE_SOURCE_TIMEOUT",
                "GitHub release-readiness 数据请求超时。",
                status_code=504,
                retryable=True,
                details={"provider": "GitHub", "path": path},
            ) from error
        except httpx.RequestError as error:
            raise ApplicationError(
                "RELEASE_SOURCE_CONNECTION_FAILED",
                "无法连接 GitHub release-readiness 数据源。",
                status_code=503,
                retryable=True,
                details={"provider": "GitHub", "path": path},
            ) from error
        except httpx.HTTPStatusError as error:
            raise ApplicationError(
                "RELEASE_SOURCE_UPSTREAM_ERROR",
                f"GitHub 返回 HTTP {error.response.status_code}。",
                status_code=502,
                retryable=error.response.status_code in {429, 500, 502, 503, 504},
                details={
                    "provider": "GitHub",
                    "path": path,
                    "upstreamStatus": error.response.status_code,
                },
            ) from error

    @staticmethod
    def _json(response: httpx.Response, *, label: str) -> Any:
        try:
            return response.json()
        except json.JSONDecodeError as error:
            raise ApplicationError(
                "RELEASE_SOURCE_INVALID",
                f"GitHub {label} 返回了不可解析的 JSON。",
                status_code=502,
                retryable=True,
            ) from error

    @staticmethod
    def _source(
        *,
        source_id: str,
        title: str,
        response: httpx.Response,
        fetched_at: str,
        revision: str,
    ) -> dict[str, Any]:
        return {
            "id": source_id,
            "provider": "GitHub",
            "title": title,
            "url": str(response.url),
            "fetchedAt": fetched_at,
            "revision": revision,
            "sha256": _sha256(response.content),
            "contentType": response.headers.get("content-type", "application/json").split(
                ";", 1
            )[0],
        }

    async def fetch_live(
        self, case_input: dict[str, Any], source_policy: CaseSourcePolicy
    ) -> dict[str, Any]:
        del source_policy
        self.calls += 1
        repository = str(case_input["repository"])
        ref = str(case_input["ref"])
        maximum = int(case_input.get("maxPullRequests", 20))
        repo_path = f"/repos/{repository}"
        repo_response, commit_response = await asyncio.gather(
            self._get(repo_path),
            self._get(f"{repo_path}/commits/{quote(ref, safe='')}"),
        )
        repository_payload = self._json(repo_response, label="repository")
        commit = self._json(commit_response, label="commit")
        if not isinstance(repository_payload, dict) or not isinstance(commit, dict):
            raise ApplicationError(
                "RELEASE_SOURCE_INVALID",
                "GitHub repository 或 commit 数据结构不符合 Contract。",
                status_code=502,
                retryable=True,
            )
        sha = str(commit.get("sha") or "")
        if not sha:
            raise ApplicationError(
                "RELEASE_SOURCE_INVALID",
                "GitHub commit 数据缺少 SHA。",
                status_code=502,
                retryable=True,
            )
        base_branch = str(
            case_input.get("baseBranch")
            or repository_payload.get("default_branch")
            or ref
        )
        checks_response, pulls_response = await asyncio.gather(
            self._get(f"{repo_path}/commits/{sha}/check-runs"),
            self._get(
                f"{repo_path}/pulls",
                params={
                    "state": "open",
                    "base": base_branch,
                    "per_page": str(maximum),
                },
            ),
        )
        checks = self._json(checks_response, label="check-runs")
        pulls = self._json(pulls_response, label="pulls")
        if not isinstance(checks, dict) or not isinstance(checks.get("check_runs"), list):
            raise ApplicationError(
                "RELEASE_SOURCE_INVALID",
                "GitHub check-runs 数据结构不符合 Contract。",
                status_code=502,
                retryable=True,
            )
        if not isinstance(pulls, list):
            raise ApplicationError(
                "RELEASE_SOURCE_INVALID",
                "GitHub pull request 数据结构不符合 Contract。",
                status_code=502,
                retryable=True,
            )
        fetched_at = _fetched_at()
        responses = [
            ("github-repository", f"{repository} repository", repo_response),
            ("github-commit", f"{repository}@{ref} commit", commit_response),
            ("github-check-runs", f"{sha} check runs", checks_response),
            ("github-open-pulls", f"{repository} open pull requests", pulls_response),
        ]
        return {
            "repository": repository_payload,
            "ref": ref,
            "baseBranch": base_branch,
            "commit": commit,
            "checkRuns": checks,
            "openPullRequests": pulls,
            "sources": [
                self._source(
                    source_id=source_id,
                    title=title,
                    response=response,
                    fetched_at=fetched_at,
                    revision=sha,
                )
                for source_id, title, response in responses
            ],
            "warnings": [],
            "rawSnapshots": {
                source_id: response.text for source_id, _title, response in responses
            },
        }

    def validate_replay(self, source_bundle: dict[str, Any], case_input: dict[str, Any]) -> None:
        expected = str(case_input["repository"]).lower()
        actual = str(source_bundle.get("repository", {}).get("full_name") or "").lower()
        if actual != expected:
            raise ApplicationError(
                "REPLAY_REPOSITORY_MISMATCH",
                "重放快照的 repository 与请求不一致。",
                status_code=409,
            )
        if str(source_bundle.get("ref") or "") != str(case_input["ref"]):
            raise ApplicationError(
                "REPLAY_REF_MISMATCH",
                "重放快照的 candidate ref 与请求不一致。",
                status_code=409,
            )
