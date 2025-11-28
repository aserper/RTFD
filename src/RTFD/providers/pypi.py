"""PyPI package metadata provider."""

from __future__ import annotations

from typing import Any, Callable, Dict

import httpx

from ..utils import serialize_response
from .base import BaseProvider, ProviderMetadata, ProviderResult


class PyPIProvider(BaseProvider):
    """Provider for PyPI package metadata."""

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="pypi",
            description="PyPI package metadata",
            expose_as_tool=True,
            tool_names=["pypi_metadata"],
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search PyPI for library metadata."""
        try:
            data = await self._fetch_metadata(library)
            return ProviderResult(success=True, data=data, provider_name="pypi")
        except httpx.HTTPStatusError as exc:
            error_msg = f"PyPI returned {exc.response.status_code}"
            return ProviderResult(success=False, error=error_msg, provider_name="pypi")
        except httpx.HTTPError as exc:
            error_msg = f"PyPI request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="pypi")

    async def _fetch_metadata(self, package: str) -> Dict[str, Any]:
        """Pull package metadata from the PyPI JSON API."""
        url = f"https://pypi.org/pypi/{package}/json"
        async with await self._http_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = resp.json()

        info = payload.get("info", {})
        return {
            "name": info.get("name"),
            "summary": info.get("summary") or "",
            "version": info.get("version"),
            "home_page": info.get("home_page"),
            "docs_url": info.get("project_urls", {}).get("Documentation")
            if isinstance(info.get("project_urls"), dict)
            else None,
            "project_urls": info.get("project_urls") or {},
        }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def pypi_metadata(package: str) -> str:
            """Retrieve PyPI package metadata including documentation URLs when available. Returns data in TOON format."""
            result = await self._fetch_metadata(package)
            return serialize_response(result)

        return {"pypi_metadata": pypi_metadata}
