"""NPM package registry provider."""

from __future__ import annotations

from typing import Any, Callable, Dict

import httpx

from ..utils import serialize_response, is_fetch_enabled
from ..content_utils import extract_sections, prioritize_sections
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
            "readme": payload.get("readme", ""),  # Include README for fetch_npm_docs
        }

    async def _fetch_npm_docs(
        self, package: str, max_bytes: int = 20480
    ) -> Dict[str, Any]:
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
                content = f"# {package}\n\n{data.get('description', 'No description available.')}\n\n"
                source = "npm_minimal"

            # Extract and prioritize sections
            sections = extract_sections(content)
            if sections:
                final_content = prioritize_sections(sections, max_bytes)
            else:
                # Fallback: simple truncation
                if len(content.encode("utf-8")) > max_bytes:
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
                "error": f"Failed to fetch docs: {str(exc)}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def npm_metadata(package: str) -> str:
            """Retrieve npm package metadata including documentation URLs when available."""
            result = await self._fetch_metadata(package)
            return serialize_response(result)

        async def fetch_npm_docs(package: str, max_bytes: int = 20480) -> str:
            """
            Fetch npm package documentation content.

            Returns README content with smart section prioritization.

            Args:
                package: npm package name
                max_bytes: Maximum content size (default ~20KB)

            Returns:
                JSON with content, size, source info
            """
            result = await self._fetch_npm_docs(package, max_bytes)
            return serialize_response(result)

        tools = {"npm_metadata": npm_metadata}
        if is_fetch_enabled():
            tools["fetch_npm_docs"] = fetch_npm_docs

        return tools
