"""PyPI package metadata provider."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import httpx

from ..utils import serialize_response, is_fetch_enabled
from ..content_utils import convert_rst_to_markdown, extract_sections, prioritize_sections
from .base import BaseProvider, ProviderMetadata, ProviderResult


class PyPIProvider(BaseProvider):
    """Provider for PyPI package metadata."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["pypi_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_pypi_docs")

        return ProviderMetadata(
            name="pypi",
            description="PyPI package metadata and documentation",
            expose_as_tool=True,
            tool_names=tool_names,
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
            "description": info.get("description") or "",
        }

    def _extract_github_url(self, project_urls: Dict[str, str]) -> Optional[str]:
        """Extract GitHub repository URL from project_urls."""
        if not project_urls:
            return None

        # Check common keys for GitHub URLs
        for key in ["Source", "Repository", "Homepage", "Code"]:
            url = project_urls.get(key, "")
            if "github.com" in url:
                return url

        return None

    async def _fetch_pypi_docs(
        self, package: str, max_bytes: int = 20480
    ) -> Dict[str, Any]:
        """
        Fetch documentation content for PyPI package.

        Args:
            package: Package name
            max_bytes: Maximum content size in bytes

        Returns:
            Dict with content, size, source, etc.
        """
        try:
            # 1. Get metadata to find description and project URLs
            metadata = await self._fetch_metadata(package)

            # 2. Try PyPI description (often reStructuredText)
            content = metadata.get("description", "")
            source = "pypi"

            # 3. Convert reST to Markdown if needed
            # Check for common reST markers
            if content and (".. " in content or "::" in content[:200]):
                content = convert_rst_to_markdown(content)

            # 4. If insufficient content, try GitHub README
            if len(content.encode("utf-8")) < 500:
                repo_url = self._extract_github_url(metadata.get("project_urls", {}))
                if repo_url:
                    # For now, note that GitHub fallback requires github provider
                    # This will be implemented after GitHub provider is updated
                    source = "pypi_minimal"

            # 5. Extract and prioritize sections
            sections = extract_sections(content)
            if sections:
                final_content = prioritize_sections(sections, max_bytes)
            else:
                final_content = content[:max_bytes] if content else ""

            return {
                "package": package,
                "content": final_content,
                "size_bytes": len(final_content.encode("utf-8")),
                "source": source,
                "truncated": len(content.encode("utf-8")) > max_bytes,
            }

        except httpx.HTTPStatusError as exc:
            return {
                "package": package,
                "content": "",
                "error": f"PyPI returned {exc.response.status_code}",
                "size_bytes": 0,
                "source": None,
            }
        except Exception as exc:
            return {
                "package": package,
                "content": "",
                "error": f"Failed to fetch docs: {str(exc)}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def pypi_metadata(package: str) -> str:
            """Retrieve PyPI package metadata including documentation URLs when available."""
            result = await self._fetch_metadata(package)
            return serialize_response(result)

        async def fetch_pypi_docs(package: str, max_bytes: int = 20480) -> str:
            """
            Fetch Python package documentation content from PyPI.

            Returns README/description content with smart section prioritization.
            Converts reStructuredText to Markdown automatically.

            Args:
                package: PyPI package name
                max_bytes: Maximum content size (default ~20KB)

            Returns:
                JSON with content, size, source info
            """
            result = await self._fetch_pypi_docs(package, max_bytes)
            return serialize_response(result)

        tools = {"pypi_metadata": pypi_metadata}
        if is_fetch_enabled():
            tools["fetch_pypi_docs"] = fetch_pypi_docs

        return tools
