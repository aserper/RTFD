"""NPM package registry provider."""

from __future__ import annotations

from typing import Any, Callable, Dict

import httpx

from ..utils import serialize_response
from .base import BaseProvider, ProviderMetadata, ProviderResult


class NpmProvider(BaseProvider):
    """Provider for npm package registry metadata."""

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="npm",
            description="npm package registry metadata",
            expose_as_tool=True,
            tool_names=["npm_metadata"],
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search npm registry for package metadata."""
        try:
            data = await self._fetch_metadata(library)
            return ProviderResult(success=True, data=data, provider_name="npm")
        except httpx.HTTPStatusError as exc:
            # 404 is expected for non-existent packages
            if exc.response.status_code == 404:
                return ProviderResult(success=False, error=None, provider_name="npm")
            error_msg = f"npm registry returned {exc.response.status_code}"
            return ProviderResult(success=False, error=error_msg, provider_name="npm")
        except httpx.HTTPError as exc:
            error_msg = f"npm registry request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="npm")

    async def _fetch_metadata(self, package: str) -> Dict[str, Any]:
        """Pull package metadata from the npm registry JSON API."""
        url = f"https://registry.npmjs.org/{package}"
        async with await self._http_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

        # Extract repository URL
        repo_url = None
        repository = payload.get("repository")
        if isinstance(repository, dict):
            repo_url = repository.get("url")
        elif isinstance(repository, str):
            repo_url = repository

        # Clean up repository URL (remove git+ prefix and .git suffix if present)
        if repo_url:
            if repo_url.startswith("git+"):
                repo_url = repo_url[4:]
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]

        # Extract documentation URL from links object or use homepage
        docs_url = payload.get("homepage")

        # Extract maintainers
        maintainers = []
        for maintainer in payload.get("maintainers", []):
            if isinstance(maintainer, dict):
                maintainers.append(
                    {
                        "name": maintainer.get("name"),
                        "email": maintainer.get("email"),
                    }
                )

        return {
            "name": payload.get("name"),
            "summary": payload.get("description") or "",
            "version": payload.get("version"),
            "home_page": payload.get("homepage"),
            "docs_url": docs_url,
            "repository": repo_url,
            "license": payload.get("license"),
            "keywords": payload.get("keywords", []),
            "maintainers": maintainers,
            "author": payload.get("author"),
        }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def npm_metadata(package: str) -> str:
            """Retrieve npm package metadata including documentation URLs when available. Returns data in TOON format."""
            result = await self._fetch_metadata(package)
            return serialize_response(result)

        return {"npm_metadata": npm_metadata}
