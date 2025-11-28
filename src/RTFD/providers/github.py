"""GitHub repository and code search provider."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import httpx

from ..utils import USER_AGENT, serialize_response
from .base import BaseProvider, ProviderMetadata, ProviderResult


class GitHubProvider(BaseProvider):
    """Provider for GitHub repository and code search."""

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="github",
            description="GitHub repository and code search",
            expose_as_tool=True,
            tool_names=["github_repo_search", "github_code_search"],
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=["GITHUB_TOKEN"],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search GitHub repos for library (used by aggregator)."""
        try:
            # Aggregator adds "python" suffix for language context
            data = await self._search_repos(f"{library} python", limit=limit)
            return ProviderResult(success=True, data=data, provider_name="github")
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200] if exc.response is not None else ""
            error_msg = f"GitHub returned {exc.response.status_code} {detail}"
            return ProviderResult(success=False, error=error_msg, provider_name="github")
        except httpx.HTTPError as exc:
            error_msg = f"GitHub request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="github")

    async def _search_repos(
        self, query: str, limit: int = 5, language: Optional[str] = "Python"
    ) -> List[Dict[str, Any]]:
        """Query GitHub's repository search API."""
        headers = self._get_headers()

        params = {"q": query, "per_page": str(limit)}
        if language:
            params["q"] = f"{query} language:{language}"

        async with await self._http_client() as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()

        repos: List[Dict[str, Any]] = []
        for item in payload.get("items", []):
            repos.append(
                {
                    "name": item.get("full_name"),
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "url": item.get("html_url"),
                    "default_branch": item.get("default_branch"),
                }
            )
            if len(repos) >= limit:
                break
        return repos

    async def _search_code(
        self, query: str, repo: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search code on GitHub; optionally scoping to a repository."""
        headers = self._get_headers()

        search_query = query
        if repo:
            search_query = f"{query} repo:{repo}"

        params = {"q": search_query, "per_page": str(limit)}
        async with await self._http_client() as client:
            resp = await client.get(
                "https://api.github.com/search/code",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()

        code_hits: List[Dict[str, Any]] = []
        for item in payload.get("items", []):
            code_hits.append(
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "repository": item.get("repository", {}).get("full_name"),
                    "url": item.get("html_url"),
                }
            )
            if len(code_hits) >= limit:
                break
        return code_hits

    def _get_headers(self) -> Dict[str, str]:
        """Build GitHub API headers with optional auth token."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def github_repo_search(
            query: str, limit: int = 5, language: Optional[str] = "Python"
        ) -> str:
            """Search GitHub repositories relevant to a library or topic. Returns data in TOON format."""
            result = await self._search_repos(query, limit=limit, language=language)
            return serialize_response(result)

        async def github_code_search(
            query: str, repo: Optional[str] = None, limit: int = 5
        ) -> str:
            """Search GitHub code (optionally scoped to a repository). Returns data in TOON format."""
            result = await self._search_code(query, repo=repo, limit=limit)
            return serialize_response(result)

        return {
            "github_repo_search": github_repo_search,
            "github_code_search": github_code_search,
        }
