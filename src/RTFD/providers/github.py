"""GitHub repository and code search provider."""

from __future__ import annotations

import base64
import os
from typing import Any, Callable, Dict, List, Optional

import httpx

from ..utils import USER_AGENT, serialize_response, is_fetch_enabled
from ..content_utils import convert_relative_urls
from .base import BaseProvider, ProviderMetadata, ProviderResult


class GitHubProvider(BaseProvider):
    """Provider for GitHub repository and code search."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["github_repo_search", "github_code_search"]
        if is_fetch_enabled():
            tool_names.append("fetch_github_readme")

        return ProviderMetadata(
            name="github",
            description="GitHub repository and code search, README fetching",
            expose_as_tool=True,
            tool_names=tool_names,
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

    async def _fetch_github_readme(
        self, owner: str, repo: str, max_bytes: int = 20480
    ) -> Dict[str, Any]:
        """
        Fetch README from GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name
            max_bytes: Maximum content size

        Returns:
            Dict with content, size, source info
        """
        try:
            headers = self._get_headers()
            url = f"https://api.github.com/repos/{owner}/{repo}/readme"

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Decode base64 content
            content = base64.b64decode(data["content"]).decode("utf-8")

            # Convert relative URLs to absolute
            # Use the blob URL for the specific branch/path
            readme_name = data.get("name", "README.md")
            readme_path = data.get("path", "")
            default_branch = "main"  # Could be fetched from repo metadata if needed

            base_url = f"https://github.com/{owner}/{repo}/blob/{default_branch}"
            if readme_path and "/" in readme_path:
                # If README is in a subdirectory
                dir_path = "/".join(readme_path.split("/")[:-1])
                base_url = f"{base_url}/{dir_path}"

            content = convert_relative_urls(content, base_url)

            # Truncate if needed
            if len(content.encode("utf-8")) > max_bytes:
                # Simple truncation for now - could use smart_truncate
                encoded = content.encode("utf-8")[:max_bytes]
                # Handle potential multi-byte character splits
                while len(encoded) > 0:
                    try:
                        content = encoded.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        encoded = encoded[:-1]
                truncated = True
            else:
                truncated = False

            return {
                "repository": f"{owner}/{repo}",
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "source": "github_readme",
                "readme_path": readme_path,
                "truncated": truncated,
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "content": "",
                "error": f"GitHub returned {exc.response.status_code}",
                "size_bytes": 0,
                "source": None,
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "content": "",
                "error": f"Failed to fetch README: {str(exc)}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def github_repo_search(
            query: str, limit: int = 5, language: Optional[str] = "Python"
        ) -> str:
            """Search GitHub repositories relevant to a library or topic."""
            result = await self._search_repos(query, limit=limit, language=language)
            return serialize_response(result)

        async def github_code_search(
            query: str, repo: Optional[str] = None, limit: int = 5
        ) -> str:
            """Search GitHub code (optionally scoped to a repository)."""
            result = await self._search_code(query, repo=repo, limit=limit)
            return serialize_response(result)

        async def fetch_github_readme(repo: str, max_bytes: int = 20480) -> str:
            """
            Fetch README and documentation from GitHub repository.

            Args:
                repo: Repository in format "owner/repo"
                max_bytes: Maximum content size (default ~20KB)

            Returns:
                JSON with README content, size, and metadata
            """
            # Parse owner/repo format
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "content": "",
                    "error": "Invalid repo format. Use 'owner/repo'",
                    "size_bytes": 0,
                    "source": None,
                }
                return serialize_response(error_result)

            owner, repo_name = parts
            result = await self._fetch_github_readme(owner, repo_name, max_bytes)
            return serialize_response(result)

        tools = {
            "github_repo_search": github_repo_search,
            "github_code_search": github_code_search,
        }
        if is_fetch_enabled():
            tools["fetch_github_readme"] = fetch_github_readme

        return tools
