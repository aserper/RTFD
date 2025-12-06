"""Zig programming language documentation provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.types import CallToolResult

from ..utils import serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class ZigProvider(BaseProvider):
    """Provider for Zig language documentation."""

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="zig",
            description="Zig programming language documentation",
            expose_as_tool=True,
            tool_names=["zig_docs"],
            supports_library_search=False,  # Zig docs are not a library/package search
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Not supported for Zig provider."""
        return ProviderResult(
            success=False,
            error="Zig provider does not support library search",
            provider_name="zig",
        )

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def zig_docs(query: str) -> CallToolResult:
            """
            Search Zig programming language documentation.

            USE THIS WHEN: You need information about Zig language features, syntax, stdlib, or concepts.

            BEST FOR: Learning Zig language specifics and finding relevant documentation sections.
            Searches the official Zig documentation (ziglang.org/documentation/master/) and returns
            matching sections with titles, summaries, and relevance scores.

            Good for queries about:
            - Language features (e.g., "comptime", "async", "optionals")
            - Standard library (e.g., "ArrayList", "HashMap", "allocators")
            - Memory management (e.g., "allocator", "defer", "errdefer")
            - Error handling (e.g., "error sets", "try", "catch")
            - Build system (e.g., "build.zig", "zig build")

            NOT SUITABLE FOR: Third-party Zig packages (use GitHub provider for that)

            Args:
                query: Search keywords (e.g., "comptime", "async", "ArrayList", "error handling")

            Returns:
                JSON with matching documentation sections, relevance scores, and source URL

            Example: zig_docs("comptime") → Returns sections about compile-time code execution
            """
            result = await self._search_zig_docs(query)
            return serialize_response_with_meta(result)

        return {"zig_docs": zig_docs}

    async def _search_zig_docs(self, query: str) -> dict[str, Any]:
        """Search Zig documentation and return relevant sections."""
        try:
            # Fetch the master documentation page
            url = "https://ziglang.org/documentation/master/"
            async with await self._http_client() as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

            # Build a search index of documentation sections
            sections = self._extract_doc_sections(soup)

            # Find matching sections based on query
            matches = self._search_sections(sections, query.lower())

            return {
                "query": query,
                "source": "https://ziglang.org/documentation/master/",
                "matches": matches[:5],  # Limit to top 5 results
                "total_matches": len(matches),
            }

        except httpx.HTTPError as exc:
            return {
                "query": query,
                "error": f"Failed to fetch Zig documentation: {exc}",
                "source": "https://ziglang.org/documentation/master/",
            }
        except Exception as exc:
            return {
                "query": query,
                "error": f"Error searching Zig documentation: {exc}",
                "source": "https://ziglang.org/documentation/master/",
            }

    def _extract_doc_sections(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract documentation sections from the page."""
        sections = []

        # Look for main headings and their content
        for heading in soup.find_all(["h1", "h2", "h3"]):
            title = heading.get_text(strip=True)
            if not title:
                continue

            # Get the next few paragraphs as summary
            summary_parts = []
            current = heading.find_next_sibling()
            for _ in range(2):  # Get up to 2 paragraphs
                if current is None:
                    break
                if current.name in ["p", "pre", "code"]:
                    text = current.get_text(strip=True)[:200]  # First 200 chars
                    if text:
                        summary_parts.append(text)
                elif current.name in ["h1", "h2", "h3"]:
                    break
                current = current.find_next_sibling()

            summary = " ".join(summary_parts)

            sections.append(
                {
                    "title": title,
                    "summary": summary,
                    "level": heading.name,
                }
            )

        return sections

    def _search_sections(self, sections: list[dict[str, str]], query: str) -> list[dict[str, Any]]:
        """Search sections for matches based on query string."""
        matches = []
        query_words = query.lower().split()

        for section in sections:
            title_lower = section["title"].lower()
            summary_lower = section["summary"].lower()

            # Score based on word matches (individual words from query)
            total_score = 0
            for word in query_words:
                # Title matches are weighted higher
                title_score = title_lower.count(word)
                summary_score = summary_lower.count(word)
                total_score += (title_score * 2) + summary_score

            if total_score > 0:
                matches.append(
                    {
                        "title": section["title"],
                        "summary": section["summary"],
                        "relevance_score": total_score,
                    }
                )

        # Sort by relevance score
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches
