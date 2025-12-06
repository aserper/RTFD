"""Rust crates.io package registry provider."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..utils import serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class CratesProvider(BaseProvider):
    """Provider for crates.io Rust package registry."""

    BASE_URL = "https://crates.io/api/v1"
    MIN_REQUEST_INTERVAL = 1.0  # crates.io enforces 1 request per second

    def __init__(self, http_client_factory: Callable):
        """Initialize provider with HTTP client factory and rate limiting."""
        super().__init__(http_client_factory)
        import asyncio

        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="crates",
            description="Rust crates.io package registry metadata",
            expose_as_tool=True,
            tool_names=["crates_metadata", "search_crates"],
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search crates.io for Rust packages."""
        try:
            data = await self._search_crates(library, per_page=limit)
            return ProviderResult(success=True, data=data, provider_name="crates")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return ProviderResult(success=False, error=None, provider_name="crates")
            error_msg = f"crates.io returned {exc.response.status_code}"
            return ProviderResult(success=False, error=error_msg, provider_name="crates")
        except httpx.HTTPError as exc:
            error_msg = f"crates.io request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="crates")
        except Exception:
            return ProviderResult(success=False, error=None, provider_name="crates")

    async def _rate_limit(self) -> None:
        """Enforce crates.io rate limit (1 request per second)."""
        async with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.MIN_REQUEST_INTERVAL:
                wait_time = self.MIN_REQUEST_INTERVAL - elapsed
                # Calculate the time when the request will be allowed
                self._last_request_time = time.time() + wait_time
                # Use async sleep equivalent via httpx timeout
                await self._async_sleep(wait_time)
            else:
                self._last_request_time = time.time()

    @staticmethod
    async def _async_sleep(seconds: float) -> None:
        """Sleep asynchronously without blocking."""
        import asyncio

        await asyncio.sleep(seconds)

    async def _search_crates(self, query: str, per_page: int = 5) -> dict[str, Any]:
        """Search for crates by name/keyword."""
        await self._rate_limit()

        try:
            async with await self._http_client() as client:
                response = await client.get(
                    f"{self.BASE_URL}/crates",
                    params={"q": query, "per_page": min(per_page, 100), "page": 1},
                )
                response.raise_for_status()
                data = response.json()

            # Format the response
            crates = data.get("crates", [])
            formatted_crates = []

            for crate in crates[:per_page]:
                formatted_crates.append(
                    {
                        "name": crate.get("name"),
                        "version": crate.get("max_version"),
                        "description": crate.get("description", ""),
                        "downloads": crate.get("downloads"),
                        "recent_downloads": crate.get("recent_downloads"),
                        "repository": crate.get("repository"),
                        "documentation": crate.get("documentation"),
                        "homepage": crate.get("homepage"),
                        "license": crate.get("license"),
                        "categories": crate.get("categories", []),
                        "keywords": crate.get("keywords", []),
                        "created_at": crate.get("created_at"),
                        "updated_at": crate.get("updated_at"),
                    }
                )

            return {
                "query": query,
                "results": formatted_crates,
                "total": data.get("meta", {}).get("total"),
                "source": "https://crates.io/",
            }

        except Exception as e:
            return {
                "query": query,
                "error": str(e),
                "source": "https://crates.io/",
            }

    async def _get_crate_metadata(self, crate_name: str) -> dict[str, Any]:
        """Get detailed metadata for a specific crate."""
        await self._rate_limit()

        try:
            async with await self._http_client() as client:
                response = await client.get(f"{self.BASE_URL}/crates/{crate_name}")
                response.raise_for_status()
                data = response.json()

            crate = data.get("crate", {})
            version = data.get("versions", [{}])[0] if data.get("versions") else {}

            return {
                "name": crate.get("name"),
                "version": crate.get("max_version"),
                "description": crate.get("description"),
                "repository": crate.get("repository"),
                "documentation": crate.get("documentation"),
                "homepage": crate.get("homepage"),
                "license": version.get("license"),
                "downloads": crate.get("downloads"),
                "recent_downloads": crate.get("recent_downloads"),
                "categories": crate.get("categories", []),
                "keywords": crate.get("keywords", []),
                "num_versions": crate.get("num_versions"),
                "created_at": crate.get("created_at"),
                "updated_at": crate.get("updated_at"),
                "rust_version": version.get("rust_version"),
                "url": f"https://crates.io/crates/{crate_name}",
            }

        except Exception as e:
            return {
                "name": crate_name,
                "error": str(e),
                "url": f"https://crates.io/crates/{crate_name}",
            }

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def search_crates(query: str, limit: int = 5) -> CallToolResult:
            """
            Search for Rust crates on crates.io by name or keywords.

            USE THIS WHEN: You need to find Rust packages/crates for a specific purpose or library.

            BEST FOR: Discovering which Rust crates exist for a topic or functionality.
            Returns multiple matching crates with names, versions, descriptions, download counts, and URLs.

            After finding a crate, use:
            - crates_metadata() to get detailed information about a specific crate
            - The documentation URL to read full docs (use WebFetch)

            Args:
                query: Search keywords (e.g., "http client", "web framework", "serde")
                limit: Maximum number of results (default 5, max 100)

            Returns:
                JSON with list of matching crates, total results, and metadata

            Example: search_crates("web framework") → Finds actix-web, rocket, axum, etc.
            """
            result = await self._search_crates(query, per_page=limit)
            return serialize_response_with_meta(result)

        async def crates_metadata(crate: str) -> CallToolResult:
            """
            Get detailed metadata for a specific Rust crate from crates.io.

            USE THIS WHEN: You need comprehensive information about a specific Rust crate.

            RETURNS: Detailed crate metadata including version, URLs, downloads, and license.
            Does NOT include full documentation content.

            The response includes:
            - Crate name, version, description
            - Documentation URL (docs.rs) - can be passed to WebFetch for full API docs
            - Repository URL (usually GitHub) - can be used with GitHub provider
            - Homepage, license, categories, keywords
            - Download statistics, creation/update dates
            - Minimum Rust version required

            Args:
                crate: Crate name (e.g., "serde", "tokio", "actix-web")

            Returns:
                JSON with comprehensive crate metadata

            Example: crates_metadata("serde") → Returns metadata with docs.rs link and GitHub repo
            """
            result = await self._get_crate_metadata(crate)
            return serialize_response_with_meta(result)

        return {"search_crates": search_crates, "crates_metadata": crates_metadata}
