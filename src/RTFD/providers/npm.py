"""NPM package registry provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..content_utils import extract_sections, prioritize_sections
from ..utils import is_fetch_enabled, serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class NpmProvider(BaseProvider):
    """Provider for npm package registry metadata."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["npm_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_npm_docs")

        return ProviderMetadata(
            name="npm",
            description="npm package registry metadata and documentation",
            expose_as_tool=True,
            tool_names=tool_names,
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

    async def _fetch_metadata(self, package: str) -> dict[str, Any]:
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
            "readme": payload.get("readme", ""),  # Include README for fetch_npm_docs
        }

    async def _fetch_npm_docs(self, package: str, max_bytes: int = 20480) -> dict[str, Any]:
        """
        Fetch documentation content for npm package.

        Args:
            package: Package name
            max_bytes: Maximum content size in bytes

        Returns:
            Dict with content, size, source info
        """
        try:
            url = f"https://registry.npmjs.org/{package}"

            async with await self._http_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            # npm registry includes README in "readme" field (already Markdown)
            content = data.get("readme", "")

            # If no README or very short, note it
            source = "npm"
            if not content or len(content.strip()) < 100:
                content = (
                    f"# {package}\n\n{data.get('description', 'No description available.')}\n\n"
                )
                source = "npm_minimal"

            # Extract and prioritize sections
            sections = extract_sections(content)
            if sections:
                final_content = prioritize_sections(sections, max_bytes)
            # Fallback: simple truncation
            elif len(content.encode("utf-8")) > max_bytes:
                encoded = content.encode("utf-8")[:max_bytes]
                # Handle multi-byte characters
                while len(encoded) > 0:
                    try:
                        final_content = encoded.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        encoded = encoded[:-1]
            else:
                final_content = content

            return {
                "package": package,
                "content": final_content,
                "size_bytes": len(final_content.encode("utf-8")),
                "source": source,
                "truncated": len(content.encode("utf-8")) > max_bytes,
                "version": data.get("version"),
            }

        except httpx.HTTPStatusError as exc:
            return {
                "package": package,
                "content": "",
                "error": f"npm registry returned {exc.response.status_code}",
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

        async def npm_metadata(package: str) -> CallToolResult:
            """
            Get npm package metadata (name, version, URLs, maintainers).

            USE THIS WHEN: You need basic package info, version numbers, or links to external documentation.

            RETURNS: Package metadata ONLY - does NOT include actual documentation content.
            For full documentation, use fetch_npm_docs instead.

            The response includes:
            - Package name, version, description
            - Documentation URL (docs_url/homepage) - can be passed to WebFetch for external docs
            - Repository URL (usually GitHub)
            - License, keywords, maintainers

            Args:
                package: npm package name (e.g., "express", "react", "lodash")

            Example: npm_metadata("express") → Returns metadata with links to expressjs.com
            """
            result = await self._fetch_metadata(package)
            return serialize_response_with_meta(result)

        async def fetch_npm_docs(package: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch actual npm package documentation from npm registry README.

            USE THIS WHEN: You need installation instructions, usage examples, API reference, or quickstart guides.

            BEST FOR: Getting complete, formatted documentation for JavaScript/Node.js packages.
            Better than using curl or WebFetch because it:
            - Automatically extracts relevant sections (Installation, Usage, Examples, API)
            - Prioritizes most useful content sections
            - Already in Markdown format (npm requires Markdown READMEs)

            NOT SUITABLE FOR: External documentation sites (use docs_url from npm_metadata + WebFetch)

            Args:
                package: npm package name (e.g., "express", "react", "axios")
                max_bytes: Maximum content size, default 20KB (increase for large packages)

            Returns:
                JSON with actual documentation content, size, truncation status, version

            Example: fetch_npm_docs("express") → Returns formatted README with installation and usage
            """
            result = await self._fetch_npm_docs(package, max_bytes)
            return serialize_response_with_meta(result)

        tools = {"npm_metadata": npm_metadata}
        if is_fetch_enabled():
            tools["fetch_npm_docs"] = fetch_npm_docs

        return tools
