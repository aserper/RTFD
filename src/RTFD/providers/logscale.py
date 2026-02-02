"""LogScale (Humio) query language documentation provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from mcp.types import CallToolResult

from ..content_utils import extract_sections, html_to_markdown, prioritize_sections
from ..utils import chunk_and_serialize_response, is_fetch_enabled, serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult, ToolTierInfo

# Base URL for LogScale documentation
BASE_URL = "https://library.humio.com/data-analysis/"

# Mapping of syntax topics to their documentation pages
SYNTAX_TOPICS = {
    "comments": {
        "page": "syntax-comments.html",
        "description": "Single-line and multi-line comment syntax",
    },
    "filters": {
        "page": "syntax-filters.html",
        "description": "Query filters and field-based filtering",
    },
    "operators": {
        "page": "syntax-operators.html",
        "description": "Logical and comparison operators",
    },
    "fields": {
        "page": "syntax-fields.html",
        "description": "Field creation, assignment, and manipulation",
    },
    "user-input": {
        "page": "syntax-fields-user-input.html",
        "description": "User-configurable parameters in queries",
    },
    "conditional": {
        "page": "syntax-conditional.html",
        "description": "Conditional evaluation with case/match statements",
    },
    "array": {
        "page": "syntax-array.html",
        "description": "Array processing and indexing",
    },
    "expressions": {
        "page": "syntax-expressions.html",
        "description": "Expression syntax and evaluation",
    },
    "user-functions": {
        "page": "syntax-function-user.html",
        "description": "User-defined functions",
    },
    "function-calls": {
        "page": "syntax-function.html",
        "description": "Function call syntax",
    },
    "time": {
        "page": "syntax-time.html",
        "description": "Time-related syntax overview",
    },
    "timezones": {
        "page": "syntax-time-timezones.html",
        "description": "Timezone handling in queries",
    },
    "relative-time": {
        "page": "syntax-time-relative.html",
        "description": "Relative time expressions",
    },
    "macros": {
        "page": "syntax-macros.html",
        "description": "Query macros and reusable components",
    },
    "regex": {
        "page": "syntax-regex.html",
        "description": "Regular expression overview",
    },
    "regex-syntax": {
        "page": "syntax-regex-syntax.html",
        "description": "Regular expression syntax reference",
    },
    "regex-flags": {
        "page": "syntax-regex-flags.html",
        "description": "Regular expression flags and modifiers",
    },
    "regex-engines": {
        "page": "syntax-regex-engines.html",
        "description": "Regular expression engine options",
    },
}

# Function categories with their documentation pages
FUNCTION_CATEGORIES = {
    "aggregate": {
        "page": "functions-aggregate.html",
        "description": "Aggregation functions (count, sum, avg, etc.)",
    },
    "array": {
        "page": "functions-array.html",
        "description": "Array manipulation functions",
    },
    "comparison": {
        "page": "functions-comparison.html",
        "description": "Comparison and equality functions",
    },
    "conditional": {
        "page": "functions-condition.html",
        "description": "Conditional logic functions",
    },
    "data-manipulation": {
        "page": "functions-data-manipulation.html",
        "description": "Data transformation functions",
    },
    "event": {
        "page": "functions-event.html",
        "description": "Event information functions",
    },
    "filter": {
        "page": "functions-filter.html",
        "description": "Filtering functions",
    },
    "formatting": {
        "page": "functions-formatting.html",
        "description": "Output formatting functions",
    },
    "geolocation": {
        "page": "functions-geolocation.html",
        "description": "Geographic and IP location functions",
    },
    "hash": {
        "page": "functions-hash-functions.html",
        "description": "Hashing functions (MD5, SHA, etc.)",
    },
    "join": {
        "page": "functions-join-functions.html",
        "description": "Data joining functions",
    },
    "math": {
        "page": "functions-math.html",
        "description": "Mathematical functions",
    },
    "network": {
        "page": "functions-network-location.html",
        "description": "Network and location functions",
    },
    "parsing": {
        "page": "functions-parsing.html",
        "description": "Data parsing functions",
    },
    "regex": {
        "page": "functions-regular-expression.html",
        "description": "Regular expression functions",
    },
    "security": {
        "page": "functions-security.html",
        "description": "Security-related functions",
    },
    "statistics": {
        "page": "functions-statistics.html",
        "description": "Statistical functions",
    },
    "string": {
        "page": "functions-string.html",
        "description": "String manipulation functions",
    },
    "time-date": {
        "page": "functions-time-date.html",
        "description": "Time and date functions",
    },
    "widget": {
        "page": "functions-widget.html",
        "description": "Dashboard widget functions",
    },
}


class LogscaleProvider(BaseProvider):
    """Provider for LogScale (Humio) query language documentation."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["search_logscale_docs", "list_logscale_functions"]
        if is_fetch_enabled():
            tool_names.extend(["logscale_syntax", "logscale_function"])

        tool_tiers = {
            "search_logscale_docs": ToolTierInfo(tier=5, defer_recommended=True, category="search"),
            "list_logscale_functions": ToolTierInfo(
                tier=5, defer_recommended=True, category="metadata"
            ),
            "logscale_syntax": ToolTierInfo(tier=5, defer_recommended=True, category="fetch"),
            "logscale_function": ToolTierInfo(tier=5, defer_recommended=True, category="fetch"),
        }

        return ProviderMetadata(
            name="logscale",
            description="LogScale (Humio) query language syntax and function documentation",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=False,
            required_env_vars=[],
            optional_env_vars=[],
            tool_tiers=tool_tiers,
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Not supported for LogScale provider."""
        return ProviderResult(
            success=False,
            error="LogScale provider does not support library search",
            provider_name="logscale",
        )

    async def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch and parse an HTML page."""
        async with await self._http_client() as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")

    async def _search_docs(self, query: str, limit: int = 10) -> dict[str, Any]:
        """
        Search LogScale documentation for matching content.

        Searches across syntax topics, function categories, and function names.
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        results: list[dict[str, Any]] = []

        # Search syntax topics
        for topic_key, topic_info in SYNTAX_TOPICS.items():
            score = 0
            for word in query_words:
                if word in topic_key:
                    score += 3
                if word in topic_info["description"].lower():
                    score += 1
            if score > 0:
                results.append(
                    {
                        "type": "syntax",
                        "name": topic_key,
                        "description": topic_info["description"],
                        "url": urljoin(BASE_URL, topic_info["page"]),
                        "score": score,
                    }
                )

        # Search function categories
        for cat_key, cat_info in FUNCTION_CATEGORIES.items():
            score = 0
            for word in query_words:
                if word in cat_key:
                    score += 3
                if word in cat_info["description"].lower():
                    score += 1
            if score > 0:
                results.append(
                    {
                        "type": "function_category",
                        "name": cat_key,
                        "description": cat_info["description"],
                        "url": urljoin(BASE_URL, cat_info["page"]),
                        "score": score,
                    }
                )

        # Try to fetch and search the main functions page for specific function names
        try:
            functions_url = urljoin(BASE_URL, "functions.html")
            soup = await self._fetch_page(functions_url)

            # Find function links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if href.startswith("functions-") and href.endswith(".html"):
                    # Skip category pages
                    if any(href == cat["page"] for cat in FUNCTION_CATEGORIES.values()):
                        continue

                    func_name = link.get_text(strip=True)
                    if not func_name:
                        continue

                    # Extract function name from URL as fallback
                    if not func_name or func_name == href:
                        func_name = href.replace("functions-", "").replace(".html", "")

                    score = 0
                    func_lower = func_name.lower()
                    for word in query_words:
                        if word in func_lower:
                            score += 5  # Higher weight for function name matches
                        if word in href.lower():
                            score += 2

                    if score > 0:
                        results.append(
                            {
                                "type": "function",
                                "name": func_name,
                                "description": f"LogScale function: {func_name}",
                                "url": urljoin(BASE_URL, href),
                                "score": score,
                            }
                        )

        except Exception:
            # Continue without function search if it fails
            pass

        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)

        # Remove score from output and deduplicate
        seen_urls = set()
        unique_results = []
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                unique_results.append(
                    {
                        "type": r["type"],
                        "name": r["name"],
                        "description": r["description"],
                        "url": r["url"],
                    }
                )
                if len(unique_results) >= limit:
                    break

        return {
            "query": query,
            "results": unique_results,
            "total_found": len(results),
            "source": BASE_URL,
        }

    async def _fetch_syntax_docs(self, topic: str, max_bytes: int = 20480) -> dict[str, Any]:
        """Fetch documentation for a specific syntax topic."""
        topic_lower = topic.lower().strip()

        # Try to find matching topic
        matched_topic = None
        matched_info = None

        # Direct match
        if topic_lower in SYNTAX_TOPICS:
            matched_topic = topic_lower
            matched_info = SYNTAX_TOPICS[topic_lower]
        else:
            # Partial match
            for key, info in SYNTAX_TOPICS.items():
                if topic_lower in key or key in topic_lower:
                    matched_topic = key
                    matched_info = info
                    break
                # Also check description
                if topic_lower in info["description"].lower():
                    matched_topic = key
                    matched_info = info
                    break

        if not matched_info:
            # List available topics
            available = ", ".join(sorted(SYNTAX_TOPICS.keys()))
            return {
                "topic": topic,
                "error": f"Topic not found. Available topics: {available}",
                "source": BASE_URL,
            }

        try:
            url = urljoin(BASE_URL, matched_info["page"])
            soup = await self._fetch_page(url)

            # Extract main content
            content = self._extract_main_content(soup, url, max_bytes)

            return {
                "topic": matched_topic,
                "description": matched_info["description"],
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "url": url,
                "source": "logscale_docs",
            }

        except httpx.HTTPStatusError as exc:
            return {
                "topic": topic,
                "error": f"HTTP error {exc.response.status_code}",
                "source": BASE_URL,
            }
        except httpx.HTTPError as exc:
            return {
                "topic": topic,
                "error": f"Failed to fetch docs: {exc}",
                "source": BASE_URL,
            }
        except Exception as exc:
            return {
                "topic": topic,
                "error": f"Error processing docs: {exc!s}",
                "source": BASE_URL,
            }

    async def _fetch_function_docs(
        self, function_name: str, max_bytes: int = 20480
    ) -> dict[str, Any]:
        """Fetch documentation for a specific LogScale function."""
        func_lower = function_name.lower().strip()

        # Normalize function name for URL
        # Handle namespaced functions like array:append -> array-append
        func_slug = func_lower.replace(":", "-").replace("()", "").replace(" ", "-")

        # Construct the function page URL
        func_url = urljoin(BASE_URL, f"functions-{func_slug}.html")

        try:
            soup = await self._fetch_page(func_url)

            # Extract main content
            content = self._extract_main_content(soup, func_url, max_bytes)

            # Try to extract function signature from the page
            signature = ""
            sig_elem = soup.find("code", class_="code-highlight")
            if sig_elem:
                signature = sig_elem.get_text(strip=True)

            return {
                "function": function_name,
                "signature": signature,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "url": func_url,
                "source": "logscale_docs",
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Try searching for the function
                search_result = await self._search_docs(function_name, limit=5)
                func_matches = [r for r in search_result["results"] if r["type"] == "function"]
                if func_matches:
                    suggestions = ", ".join(m["name"] for m in func_matches[:3])
                    return {
                        "function": function_name,
                        "error": f"Function not found. Did you mean: {suggestions}?",
                        "suggestions": func_matches[:3],
                        "source": BASE_URL,
                    }
                return {
                    "function": function_name,
                    "error": "Function not found",
                    "source": BASE_URL,
                }
            return {
                "function": function_name,
                "error": f"HTTP error {exc.response.status_code}",
                "source": BASE_URL,
            }
        except httpx.HTTPError as exc:
            return {
                "function": function_name,
                "error": f"Failed to fetch docs: {exc}",
                "source": BASE_URL,
            }
        except Exception as exc:
            return {
                "function": function_name,
                "error": f"Error processing docs: {exc!s}",
                "source": BASE_URL,
            }

    async def _list_functions(self, category: str | None = None) -> dict[str, Any]:
        """List available LogScale functions, optionally filtered by category."""
        if category:
            cat_lower = category.lower().strip()

            # Find matching category
            matched_cat = None
            matched_info = None

            if cat_lower in FUNCTION_CATEGORIES:
                matched_cat = cat_lower
                matched_info = FUNCTION_CATEGORIES[cat_lower]
            else:
                for key, info in FUNCTION_CATEGORIES.items():
                    if cat_lower in key or key in cat_lower:
                        matched_cat = key
                        matched_info = info
                        break

            if not matched_info:
                available = ", ".join(sorted(FUNCTION_CATEGORIES.keys()))
                return {
                    "error": f"Category not found. Available: {available}",
                    "categories": list(FUNCTION_CATEGORIES.keys()),
                    "source": BASE_URL,
                }

            # Fetch category page to list functions
            try:
                url = urljoin(BASE_URL, matched_info["page"])
                soup = await self._fetch_page(url)

                functions = []
                # Find function entries in the category page
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    if href.startswith("functions-") and href.endswith(".html"):
                        # Skip category pages
                        if any(href == cat["page"] for cat in FUNCTION_CATEGORIES.values()):
                            continue

                        func_name = link.get_text(strip=True)
                        if func_name and func_name != href:
                            functions.append(
                                {
                                    "name": func_name,
                                    "url": urljoin(BASE_URL, href),
                                }
                            )

                # Deduplicate
                seen = set()
                unique_functions = []
                for f in functions:
                    if f["name"] not in seen:
                        seen.add(f["name"])
                        unique_functions.append(f)

                return {
                    "category": matched_cat,
                    "description": matched_info["description"],
                    "functions": unique_functions,
                    "count": len(unique_functions),
                    "url": url,
                    "source": "logscale_docs",
                }

            except Exception as exc:
                return {
                    "category": category,
                    "error": f"Failed to fetch category: {exc!s}",
                    "source": BASE_URL,
                }

        # No category specified - return all categories
        return {
            "categories": [
                {
                    "name": key,
                    "description": info["description"],
                    "url": urljoin(BASE_URL, info["page"]),
                }
                for key, info in sorted(FUNCTION_CATEGORIES.items())
            ],
            "total_categories": len(FUNCTION_CATEGORIES),
            "source": BASE_URL,
            "hint": "Use category parameter to list functions in a specific category",
        }

    def _extract_main_content(self, soup: BeautifulSoup, base_url: str, max_bytes: int) -> str:
        """Extract and process main content from a documentation page."""
        # Make a copy to avoid modifying the original soup
        from copy import copy

        soup = copy(soup)

        # Remove unwanted elements first (before finding content)
        for unwanted in soup.find_all(
            ["nav", "aside", "footer", "header", "script", "style", "noscript"]
        ):
            unwanted.decompose()

        # Remove elements by class patterns common in Humio docs
        unwanted_patterns = [
            "nav",
            "sidebar",
            "menu",
            "breadcrumb",
            "toc",
            "footer",
            "header",
            "skip",
            "social",
            "share",
            "cookie",
            "banner",
        ]
        for pattern in unwanted_patterns:
            for elem in soup.find_all(class_=lambda x, p=pattern: x and p in str(x).lower()):
                elem.decompose()
            for elem in soup.find_all(id=lambda x, p=pattern: x and p in str(x).lower()):
                elem.decompose()

        # Try to find the main content area using multiple strategies
        main_content = None

        # Strategy 1: Look for main/article tags
        main_content = soup.find("main")
        if not main_content:
            main_content = soup.find("article")

        # Strategy 2: Look for content div with specific classes
        if not main_content:
            for class_name in ["content", "doc-content", "documentation", "page-content"]:
                main_content = soup.find("div", class_=class_name)
                if main_content:
                    break

        # Strategy 3: Find the first H1 or H2 and get its parent container
        if not main_content:
            heading = soup.find(["h1", "h2"])
            if heading:
                # Walk up to find a reasonable container
                parent = heading.parent
                while parent and parent.name not in ["body", "html", None]:
                    # If parent has substantial content, use it
                    if len(parent.get_text(strip=True)) > 500:
                        main_content = parent
                        break
                    parent = parent.parent

        # Strategy 4: Fall back to body
        if not main_content:
            main_content = soup.find("body")

        if not main_content:
            return "Unable to extract content from page"

        # Extract content - focus on headings, paragraphs, tables, code blocks, and lists
        content_parts = []

        # Get the page title from H1 or H2
        title_elem = main_content.find(["h1", "h2"])
        if title_elem:
            content_parts.append(f"## {title_elem.get_text(strip=True)}\n")

        # Process content elements in order
        for elem in main_content.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "pre", "code", "ul", "ol", "dl"]
        ):
            # Skip if already processed as title
            if elem == title_elem:
                continue

            # Skip empty elements
            text = elem.get_text(strip=True)
            if not text:
                continue

            # Skip navigation-like lists (short items with mostly links)
            if elem.name in ["ul", "ol"]:
                items = elem.find_all("li")
                if items:
                    link_count = sum(1 for li in items if li.find("a"))
                    avg_len = sum(len(li.get_text(strip=True)) for li in items) / len(items)
                    # Skip if most items are just links and short
                    if link_count / len(items) > 0.8 and avg_len < 50:
                        continue

            # Convert element to markdown
            elem_html = str(elem)
            elem_md = html_to_markdown(elem_html, base_url)
            if elem_md.strip():
                content_parts.append(elem_md)

        # Join content
        markdown_content = "\n\n".join(content_parts)

        # If we got very little content, try a simpler approach
        if len(markdown_content) < 200:
            html_content = str(main_content)
            markdown_content = html_to_markdown(html_content, base_url)

        # Extract and prioritize sections
        sections = extract_sections(markdown_content)
        if sections:
            final_content = prioritize_sections(sections, max_bytes)
        elif len(markdown_content.encode("utf-8")) > max_bytes:
            # Simple truncation for content without sections
            encoded = markdown_content.encode("utf-8")[:max_bytes]
            while len(encoded) > 0:
                try:
                    final_content = encoded.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    encoded = encoded[:-1]
            else:
                final_content = ""
        else:
            final_content = markdown_content

        return final_content

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def search_logscale_docs(query: str, limit: int = 10) -> CallToolResult:
            """
            Search LogScale query language docs for syntax, functions, operators.

            When: Learning LogScale/Humio query syntax or finding functions
            Searches: Syntax topics, function names, categories
            Args: query="regex", limit=10
            Ex: search_logscale_docs("time") → matching syntax/functions
            """
            result = await self._search_docs(query, limit=limit)
            return serialize_response_with_meta(result)

        async def list_logscale_functions(
            category: str | None = None,
        ) -> CallToolResult:
            """
            List LogScale functions by category. Without category, lists all categories.

            Categories: aggregate, array, string, math, time-date, regex, parsing, hash, etc.
            Args: category="string" or category=None for all categories
            Ex: list_logscale_functions("math") → math functions list
            """
            result = await self._list_functions(category)
            return serialize_response_with_meta(result)

        async def logscale_syntax(topic: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch LogScale syntax docs for a topic (filters, operators, regex, time, etc.).

            Topics: comments, filters, operators, fields, conditional, array, regex, time, macros
            Args: topic="regex", max_bytes=20480
            Ex: logscale_syntax("filters") → filter syntax documentation
            """
            result = await self._fetch_syntax_docs(topic, max_bytes)
            return chunk_and_serialize_response(result)

        async def logscale_function(function_name: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch docs for a specific LogScale function (regex, split, count, etc.).

            Args: function_name="regex" or "array:append", max_bytes=20480
            Ex: logscale_function("splitString") → function signature, params, examples
            """
            result = await self._fetch_function_docs(function_name, max_bytes)
            return chunk_and_serialize_response(result)

        tools: dict[str, Callable] = {
            "search_logscale_docs": search_logscale_docs,
            "list_logscale_functions": list_logscale_functions,
        }

        if is_fetch_enabled():
            tools["logscale_syntax"] = logscale_syntax
            tools["logscale_function"] = logscale_function

        return tools
