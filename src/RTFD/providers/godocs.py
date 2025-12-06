"""GoDocs package metadata provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.types import CallToolResult

from ..utils import is_fetch_enabled, serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class GoDocsProvider(BaseProvider):
    """Provider for GoDocs package metadata."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["godocs_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_godocs_docs")

        return ProviderMetadata(
            name="godocs",
            description="GoDocs package documentation metadata",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search GoDocs for library metadata."""
        try:
            data = await self._fetch_metadata(library)
            return ProviderResult(success=True, data=data, provider_name="godocs")
        except httpx.HTTPStatusError as exc:
            # 404 is expected for non-Go packages - don't report as error
            if exc.response.status_code == 404:
                return ProviderResult(success=False, error=None, provider_name="godocs")
            error_msg = f"GoDocs returned {exc.response.status_code}"
            return ProviderResult(success=False, error=error_msg, provider_name="godocs")
        except httpx.HTTPError as exc:
            error_msg = f"GoDocs request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="godocs")
        except Exception:
            # Parsing errors - silent fail
            return ProviderResult(success=False, error=None, provider_name="godocs")

    async def _fetch_metadata(self, package: str) -> dict[str, Any]:
        """Scrape package metadata from godocs.io."""
        # Handle full URLs or just package paths
        if package.startswith("https://godocs.io/"):
            package = package.replace("https://godocs.io/", "")

        # godocs.io seems to block standard browser User-Agents but allows curl.
        # We'll use a curl-like User-Agent for this specific request.
        url = f"https://godocs.io/{package}"
        headers = {"User-Agent": "curl/7.68.0"}
        async with await self._http_client() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

        # Extract description/synopsis
        description = ""

        # Try meta description first
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        # If meta description is missing or generic, try parsing the body
        # The structure is usually: <h2 id="pkg-overview">...</h2> <p>import ...</p> <p>Description...</p>
        if not description or "godocs.io" in description:
            overview_header = soup.find(["h2", "h3"], {"id": "pkg-overview"})
            if overview_header:
                # Look at next siblings
                for sibling in overview_header.find_next_siblings():
                    if sibling.name in ("h2", "h3"):  # Stop at next section
                        break
                    if sibling.name == "p":
                        text = sibling.get_text(strip=True)
                        # Skip the import statement
                        if text.startswith('import "'):
                            continue
                        description = text
                        break

        return {
            "name": package,
            "summary": description,
            "url": url,
            "source_url": f"https://pkg.go.dev/{package}",  # godocs often mirrors standard paths
        }

    async def _fetch_godocs_docs(self, package: str, max_bytes: int = 20480) -> dict[str, Any]:
        """
        Fetch full documentation content for a Go package from godocs.io.

        Args:
            package: Package name (e.g., 'github.com/user/repo')
            max_bytes: Maximum content size in bytes

        Returns:
            Dict with content, size, source, etc.
        """
        try:
            # Handle full URLs or just package paths
            if package.startswith("https://godocs.io/"):
                package = package.replace("https://godocs.io/", "")

            url = f"https://godocs.io/{package}"
            headers = {"User-Agent": "curl/7.68.0"}

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

            # Extract comprehensive documentation content
            content_parts = []

            # 1. Get package overview/description
            overview_header = soup.find(["h2", "h3"], {"id": "pkg-overview"})
            if overview_header:
                for sibling in overview_header.find_next_siblings():
                    if sibling.name in ("h2", "h3"):
                        break
                    if sibling.name in ("p", "pre"):
                        text = sibling.get_text(strip=True)
                        if text and not text.startswith('import "'):
                            content_parts.append(text)

            # 2. Get function/type documentation (first few entries)
            # Look for main content section
            main_content = soup.find("div", class_=["container", "main"])
            if not main_content:
                main_content = soup.find("div", id="main")

            if main_content:
                # Extract text content, limit to avoid huge outputs
                text_content = main_content.get_text(separator="\n", strip=True)
                # Clean up excessive whitespace
                lines = [line.strip() for line in text_content.split("\n") if line.strip()]
                content_parts.extend(lines[:50])  # Limit to 50 lines of main content

            # Combine and truncate
            full_content = "\n".join(content_parts)

            # Encode and truncate if necessary
            content_bytes = full_content.encode("utf-8")
            if len(content_bytes) > max_bytes:
                full_content = full_content[:max_bytes]
                truncated = True
            else:
                truncated = False

            return {
                "package": package,
                "content": full_content,
                "size_bytes": len(full_content.encode("utf-8")),
                "source": "godocs",
                "truncated": truncated,
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {
                    "package": package,
                    "content": "",
                    "error": "Package not found on GoDocs",
                    "size_bytes": 0,
                    "source": None,
                }
            return {
                "package": package,
                "content": "",
                "error": f"GoDocs returned {exc.response.status_code}",
                "size_bytes": 0,
                "source": None,
            }
        except httpx.HTTPError as exc:
            return {
                "package": package,
                "content": "",
                "error": f"GoDocs request failed: {exc}",
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

        async def godocs_metadata(package: str) -> CallToolResult:
            """
            Get Go package metadata from godocs.io (name, summary, URLs).

            USE THIS WHEN: You need basic package info or links to documentation sites.

            RETURNS: Package metadata ONLY - does NOT include actual documentation content.
            For full documentation, use fetch_godocs_docs instead.

            The response includes:
            - Package name and summary/description
            - godocs.io URL
            - pkg.go.dev source URL

            Args:
                package: Go package path (e.g., "github.com/gin-gonic/gin", "golang.org/x/tools")

            Example: godocs_metadata("github.com/gin-gonic/gin") → Returns metadata with summary
            """
            result = await self._fetch_metadata(package)
            return serialize_response_with_meta(result)

        async def fetch_godocs_docs(package: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch actual Go package documentation from godocs.io.

            USE THIS WHEN: You need package overview, function signatures, type definitions, or API reference.

            BEST FOR: Getting complete documentation for Go packages.
            Better than using curl or WebFetch because it:
            - Extracts package overview and descriptions
            - Includes function and type documentation
            - Formats content in readable text format
            - Limits output to avoid overwhelming context

            NOT SUITABLE FOR: Source code (use GitHub provider for that)

            Args:
                package: Go package path (e.g., "github.com/gin-gonic/gin", "golang.org/x/sync")
                max_bytes: Maximum content size, default 20KB (increase for large packages)

            Returns:
                JSON with documentation content, size, truncation status, and source info

            Example: fetch_godocs_docs("github.com/gin-gonic/gin") → Returns overview and API docs
            """
            result = await self._fetch_godocs_docs(package, max_bytes)
            return serialize_response_with_meta(result)

        tools = {"godocs_metadata": godocs_metadata}
        if is_fetch_enabled():
            tools["fetch_godocs_docs"] = fetch_godocs_docs

        return tools
