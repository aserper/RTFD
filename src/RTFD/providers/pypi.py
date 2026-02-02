"""PyPI package metadata provider."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..content_utils import convert_rst_to_markdown, extract_sections, prioritize_sections
from ..utils import (
    chunk_and_serialize_response,
    is_fetch_enabled,
    safe_json_loads,
    serialize_response_with_meta,
)
from .base import BaseProvider, ProviderMetadata, ProviderResult, ToolTierInfo


class PyPIProvider(BaseProvider):
    """Provider for PyPI package metadata."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["pypi_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_pypi_docs")

        # Tool tier classification for defer_loading recommendations
        tool_tiers = {
            "pypi_metadata": ToolTierInfo(tier=2, defer_recommended=True, category="metadata"),
            "fetch_pypi_docs": ToolTierInfo(tier=3, defer_recommended=True, category="fetch"),
        }

        return ProviderMetadata(
            name="pypi",
            description="PyPI package metadata and documentation",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=["VERIFIED_BY_PYPI"],
            tool_tiers=tool_tiers,
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

    async def _check_verification(self, package: str) -> bool:
        """
        Check if a package is verified by PyPI.

        Fetches the project page and checks for the 'verified' class.
        """
        url = f"https://pypi.org/project/{package}/"
        try:
            async with await self._http_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                # Simple check for the verified class in the HTML
                return 'class="sidebar-section verified"' in resp.text
        except Exception:
            # If we can't check, assume unverified or fail safe?
            # Let's assume unverified to be safe if verification is required.
            return False

    async def _fetch_metadata(
        self, package: str, ignore_verification: bool = False
    ) -> dict[str, Any]:
        """Pull package metadata from the PyPI JSON API."""
        # Check verification if enabled
        if os.getenv("VERIFIED_BY_PYPI", "").lower() == "true" and not ignore_verification:
            is_verified = await self._check_verification(package)
            if not is_verified:
                return {
                    "name": package,
                    "error": f"Project '{package}' is not verified by PyPI. "
                    "Please ask the user if they want to trust this project.",
                    "is_unverified": True,
                }

        url = f"https://pypi.org/pypi/{package}/json"
        async with await self._http_client() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            payload = safe_json_loads(resp.text)

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

    def _extract_github_url(self, project_urls: dict[str, str]) -> str | None:
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
        self, package: str, max_bytes: int = 20480, ignore_verification: bool = False
    ) -> dict[str, Any]:
        """
        Fetch documentation content for PyPI package.

        Args:
            package: Package name
            max_bytes: Maximum content size in bytes
            ignore_verification: Whether to ignore PyPI verification status

        Returns:
            Dict with content, size, source, etc.
        """
        try:
            # 1. Get metadata to find description and project URLs
            # This will also perform the verification check
            metadata = await self._fetch_metadata(package, ignore_verification)

            if metadata.get("error"):
                return {
                    "package": package,
                    "content": "",
                    "error": metadata["error"],
                    "size_bytes": 0,
                    "source": None,
                }

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
                    # source = "pypi_minimal"
                    pass

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
                "error": f"Failed to fetch docs: {exc!s}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def pypi_metadata(package: str, ignore_verification: bool = False) -> CallToolResult:
            """
            Get PyPI package metadata (name, version, URLs). For docs content, use fetch_pypi_docs.

            When: Need package info or external doc links
            Args: package="requests", ignore_verification=False
            Ex: pypi_metadata("flask") → {name, version, docs_url, homepage}
            """
            result = await self._fetch_metadata(package, ignore_verification)
            return serialize_response_with_meta(result)

        async def fetch_pypi_docs(
            package: str, max_bytes: int = 20480, ignore_verification: bool = False
        ) -> CallToolResult:
            """
            Fetch Python package docs from PyPI README. Extracts relevant sections, converts RST to MD.

            When: Need installation, usage examples, or API quickstart
            Not for: External doc sites (use pypi_metadata docs_url + WebFetch)
            Args: package="requests", max_bytes=20480, ignore_verification=False
            Ex: fetch_pypi_docs("numpy") → formatted README content
            """
            result = await self._fetch_pypi_docs(package, max_bytes, ignore_verification)
            return chunk_and_serialize_response(result)

        tools = {"pypi_metadata": pypi_metadata}
        if is_fetch_enabled():
            tools["fetch_pypi_docs"] = fetch_pypi_docs

        return tools
