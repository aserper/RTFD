"""Google Cloud Platform documentation provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from bs4 import BeautifulSoup
from mcp.types import CallToolResult

from ..content_utils import extract_sections, html_to_markdown, prioritize_sections
from ..utils import (
    USER_AGENT,
    get_github_token,
    is_fetch_enabled,
    serialize_response_with_meta,
)
from .base import BaseProvider, ProviderMetadata, ProviderResult

# Mapping of common GCP services to their documentation URLs
GCP_SERVICE_DOCS = {
    "storage": {
        "name": "Cloud Storage",
        "url": "https://cloud.google.com/storage/docs",
        "api": "storage.googleapis.com",
        "description": "Object storage for companies of all sizes",
    },
    "compute": {
        "name": "Compute Engine",
        "url": "https://cloud.google.com/compute/docs",
        "api": "compute.googleapis.com",
        "description": "Virtual machines running in Google's data centers",
    },
    "bigquery": {
        "name": "BigQuery",
        "url": "https://cloud.google.com/bigquery/docs",
        "api": "bigquery.googleapis.com",
        "description": "Serverless, highly scalable, and cost-effective multicloud data warehouse",
    },
    "cloudfunctions": {
        "name": "Cloud Functions",
        "url": "https://cloud.google.com/functions/docs",
        "api": "cloudfunctions.googleapis.com",
        "description": "Event-driven serverless compute platform",
    },
    "run": {
        "name": "Cloud Run",
        "url": "https://cloud.google.com/run/docs",
        "api": "run.googleapis.com",
        "description": "Fully managed compute platform for deploying and scaling containerized applications",
    },
    "pubsub": {
        "name": "Pub/Sub",
        "url": "https://cloud.google.com/pubsub/docs",
        "api": "pubsub.googleapis.com",
        "description": "Asynchronous and scalable messaging service",
    },
    "firestore": {
        "name": "Cloud Firestore",
        "url": "https://cloud.google.com/firestore/docs",
        "api": "firestore.googleapis.com",
        "description": "NoSQL document database for mobile, web, and server development",
    },
    "datastore": {
        "name": "Cloud Datastore",
        "url": "https://cloud.google.com/datastore/docs",
        "api": "datastore.googleapis.com",
        "description": "Highly scalable NoSQL database for web and mobile applications",
    },
    "bigtable": {
        "name": "Cloud Bigtable",
        "url": "https://cloud.google.com/bigtable/docs",
        "api": "bigtable.googleapis.com",
        "description": "Fully managed, scalable NoSQL database service for large analytical and operational workloads",
    },
    "spanner": {
        "name": "Cloud Spanner",
        "url": "https://cloud.google.com/spanner/docs",
        "api": "spanner.googleapis.com",
        "description": "Fully managed, mission-critical, relational database service with transactional consistency",
    },
    "sql": {
        "name": "Cloud SQL",
        "url": "https://cloud.google.com/sql/docs",
        "api": "sqladmin.googleapis.com",
        "description": "Fully managed relational database service for MySQL, PostgreSQL, and SQL Server",
    },
    "gke": {
        "name": "Google Kubernetes Engine",
        "url": "https://cloud.google.com/kubernetes-engine/docs",
        "api": "container.googleapis.com",
        "description": "Managed Kubernetes service for running containerized applications",
    },
    "appengine": {
        "name": "App Engine",
        "url": "https://cloud.google.com/appengine/docs",
        "api": "appengine.googleapis.com",
        "description": "Platform for building scalable web applications and mobile backends",
    },
    "vision": {
        "name": "Cloud Vision API",
        "url": "https://cloud.google.com/vision/docs",
        "api": "vision.googleapis.com",
        "description": "Image analysis powered by machine learning",
    },
    "speech": {
        "name": "Cloud Speech-to-Text",
        "url": "https://cloud.google.com/speech-to-text/docs",
        "api": "speech.googleapis.com",
        "description": "Speech to text conversion powered by machine learning",
    },
    "translate": {
        "name": "Cloud Translation API",
        "url": "https://cloud.google.com/translate/docs",
        "api": "translate.googleapis.com",
        "description": "Dynamically translate between languages",
    },
    "monitoring": {
        "name": "Cloud Monitoring",
        "url": "https://cloud.google.com/monitoring/docs",
        "api": "monitoring.googleapis.com",
        "description": "Visibility into the performance, availability, and health of your applications",
    },
    "logging": {
        "name": "Cloud Logging",
        "url": "https://cloud.google.com/logging/docs",
        "api": "logging.googleapis.com",
        "description": "Store, search, analyze, monitor, and alert on logging data and events",
    },
    "iam": {
        "name": "Identity and Access Management",
        "url": "https://cloud.google.com/iam/docs",
        "api": "iam.googleapis.com",
        "description": "Manage access control by defining who (identity) has what access (role) for which resource",
    },
    "secretmanager": {
        "name": "Secret Manager",
        "url": "https://cloud.google.com/secret-manager/docs",
        "api": "secretmanager.googleapis.com",
        "description": "Store and manage access to secrets",
    },
}


class GcpProvider(BaseProvider):
    """Provider for Google Cloud Platform documentation."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["search_gcp_services"]
        if is_fetch_enabled():
            tool_names.append("fetch_gcp_service_docs")

        return ProviderMetadata(
            name="gcp",
            description="Google Cloud Platform API and service documentation",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=["GITHUB_TOKEN", "GITHUB_AUTH"],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search for GCP services (used by aggregator)."""
        try:
            data = await self._search_services(library, limit=limit)
            return ProviderResult(success=True, data=data, provider_name="gcp")
        except httpx.HTTPStatusError as exc:
            # 404 is expected for non-GCP queries - don't report as error
            if exc.response.status_code == 404:
                return ProviderResult(success=False, error=None, provider_name="gcp")
            detail = exc.response.text[:200] if exc.response is not None else ""
            error_msg = f"GitHub API returned {exc.response.status_code}: {detail}"
            return ProviderResult(success=False, error=error_msg, provider_name="gcp")
        except httpx.HTTPError as exc:
            error_msg = f"GitHub API request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="gcp")
        except Exception:
            # Parsing errors or other issues - silent fail
            return ProviderResult(success=False, error=None, provider_name="gcp")

    def _normalize_service_name(self, query: str) -> str | None:
        """
        Normalize service name to match our mapping keys.

        Args:
            query: User query (e.g., "cloud storage", "gke", "kubernetes")

        Returns:
            Normalized service key or None if not found
        """
        query_lower = query.lower().strip()

        # Direct match
        if query_lower in GCP_SERVICE_DOCS:
            return query_lower

        # Remove "cloud" and "google" prefixes
        for prefix in ["google cloud ", "cloud ", "gcp ", "google "]:
            if query_lower.startswith(prefix):
                query_lower = query_lower[len(prefix) :]

        # Check again after normalization
        if query_lower in GCP_SERVICE_DOCS:
            return query_lower

        # Common aliases
        aliases = {
            "kubernetes": "gke",
            "k8s": "gke",
            "functions": "cloudfunctions",
            "cloudrun": "run",
            "pub/sub": "pubsub",
            "cloud functions": "cloudfunctions",
            "cloud run": "run",
            "cloud storage": "storage",
            "compute engine": "compute",
            "big query": "bigquery",
            "app engine": "appengine",
            "secret manager": "secretmanager",
        }

        return aliases.get(query_lower)

    async def _search_services(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search for GCP services using GitHub API and local mapping.

        Args:
            query: Search query (e.g., "storage", "compute", "bigquery", "gke audit")
            limit: Maximum number of results to return

        Returns:
            List of matching services with metadata
        """
        results: list[dict[str, Any]] = []

        # First, check if query matches any known service
        normalized = self._normalize_service_name(query)
        if normalized and normalized in GCP_SERVICE_DOCS:
            service_info = GCP_SERVICE_DOCS[normalized]
            results.append(
                {
                    "name": service_info["name"],
                    "description": service_info["description"],
                    "api": service_info["api"],
                    "docs_url": service_info["url"],
                    "source": "gcp_mapping",
                }
            )

        # Search our local mapping for partial matches
        query_lower = query.lower()

        # If query has multiple words (e.g., "gke audit"), try first word as service
        query_words = query_lower.split()
        if len(query_words) > 1 and not results:
            # Try to find service from first word
            first_word_normalized = self._normalize_service_name(query_words[0])
            if first_word_normalized and first_word_normalized in GCP_SERVICE_DOCS:
                service_info = GCP_SERVICE_DOCS[first_word_normalized]
                # Add note about topic in description
                topic = " ".join(query_words[1:])
                results.append(
                    {
                        "name": service_info["name"],
                        "description": f"{service_info['description']} (searching for: {topic})",
                        "api": service_info["api"],
                        "docs_url": service_info["url"],
                        "source": "gcp_mapping_contextual",
                    }
                )

        # Search for partial matches in service names and descriptions
        for key, service_info in GCP_SERVICE_DOCS.items():
            # Skip if already added
            if normalized == key:
                continue
            if len(query_words) > 1 and self._normalize_service_name(query_words[0]) == key:
                continue

            # Check if ANY word in query matches service name, key, or description
            query_matches = False
            for word in query_words:
                if len(word) > 2:  # Skip very short words
                    if (
                        word in service_info["name"].lower()
                        or word in key
                        or word in service_info["description"].lower()
                    ):
                        query_matches = True
                        break

            if query_matches:
                results.append(
                    {
                        "name": service_info["name"],
                        "description": service_info["description"],
                        "api": service_info["api"],
                        "docs_url": service_info["url"],
                        "source": "gcp_mapping",
                    }
                )

            if len(results) >= limit:
                break

        # If we have results from local mapping (either exact or partial matches),
        # prioritize those over external searches
        if results:
            return results[:limit]

        # Only search cloud.google.com if we don't have local matches
        # This is for very specific queries that aren't in our mapping
        try:
            cloud_results = await self._search_cloud_google_com(query, limit)
            if cloud_results:
                results.extend(cloud_results)
        except Exception:
            pass

        if len(results) >= limit:
            return results[:limit]

        # Finally, try GitHub API search for googleapis repository
        try:
            github_results = await self._search_github_googleapis(query, limit)
            results.extend(github_results)
        except Exception:
            pass

        return results[:limit]

    async def _search_github_googleapis(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search googleapis GitHub repository for service definitions.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of service metadata from GitHub
        """
        headers = self._get_github_headers()

        # Search for proto files in googleapis repository
        search_query = f"{query} repo:googleapis/googleapis path:google/cloud"
        params = {"q": search_query, "per_page": str(limit)}

        async with await self._http_client() as client:
            resp = await client.get(
                "https://api.github.com/search/code",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()

        results: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            # Extract service name from path (e.g., google/cloud/storage/v1)
            path = item.get("path", "")
            parts = path.split("/")

            if len(parts) >= 3 and parts[0] == "google" and parts[1] == "cloud":
                service_name = parts[2]
                # Try to find in our mapping
                service_info = GCP_SERVICE_DOCS.get(service_name)

                if service_info:
                    results.append(
                        {
                            "name": service_info["name"],
                            "description": service_info["description"],
                            "api": service_info["api"],
                            "docs_url": service_info["url"],
                            "source": "github_googleapis",
                        }
                    )
                else:
                    # Generic result for unknown services
                    results.append(
                        {
                            "name": service_name.title(),
                            "description": f"Google Cloud {service_name} service",
                            "api": f"{service_name}.googleapis.com",
                            "docs_url": f"https://cloud.google.com/{service_name}/docs",
                            "source": "github_googleapis",
                        }
                    )

            if len(results) >= limit:
                break

        return results

    def _get_github_headers(self) -> dict[str, str]:
        """Build GitHub API headers with optional auth token."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = get_github_token()
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    async def _search_cloud_google_com(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search cloud.google.com for documentation.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of service metadata from search results
        """
        url = f"https://cloud.google.com/search?q={query}"
        headers = {"User-Agent": USER_AGENT}

        try:
            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

            results: list[dict[str, Any]] = []

            # Use the robust selector strategy found during testing
            search_links = soup.find_all("a", attrs={"track-type": "search-result"})

            for link in search_links:
                title = link.get_text().strip()
                href = link.get("href")

                if not href or not title:
                    continue

                # Ensure absolute URL
                if href.startswith("/"):
                    href = f"https://cloud.google.com{href}"

                # Try to extract description
                description = f"Search result for {query}"
                try:
                    container = link.parent.parent
                    full_text = container.get_text(" ", strip=True)
                    # Simple heuristic to get description part
                    desc_text = full_text.replace(title, "", 1).strip()
                    if desc_text:
                        description = desc_text[:200] + "..." if len(desc_text) > 200 else desc_text
                except Exception:
                    pass

                results.append(
                    {
                        "name": title,
                        "description": description,
                        "api": "",  # No API info from search
                        "docs_url": href,
                        "source": "cloud_google_com",
                    }
                )

                if len(results) >= limit:
                    break

            return results

        except Exception:
            # Log error or just return empty? For now return empty to be safe
            return []

    async def _fetch_service_docs(self, service: str, max_bytes: int = 20480) -> dict[str, Any]:
        """
        Fetch documentation for a specific GCP service.

        Args:
            service: Service name (e.g., "storage", "compute", "Cloud Storage")
            max_bytes: Maximum content size in bytes

        Returns:
            Dict with content, size, source info
        """
        try:
            # Normalize service name
            normalized = self._normalize_service_name(service)

            # If not found in mapping, try to construct URL
            if normalized and normalized in GCP_SERVICE_DOCS:
                service_info = GCP_SERVICE_DOCS[normalized]
                docs_url = service_info["url"]
                service_name = service_info["name"]
            else:
                # Try to search for the service
                search_results = await self._search_services(service, limit=1)
                if search_results:
                    # Use the best match
                    best_match = search_results[0]
                    docs_url = best_match["docs_url"]
                    service_name = best_match["name"]
                else:
                    # Try to construct URL from service name as a last resort
                    service_slug = service.lower().replace(" ", "-").replace("_", "-")
                    docs_url = f"https://cloud.google.com/{service_slug}/docs"
                    service_name = service

            # Fetch and parse HTML documentation
            headers = {"User-Agent": USER_AGENT}
            async with await self._http_client() as client:
                resp = await client.get(docs_url, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

            # Extract main documentation content

            # Try to find main content area
            # GCP docs typically use <main> or specific div classes
            main_content = soup.find("main")
            if not main_content:
                main_content = soup.find("div", class_=["devsite-article-body"])
            if not main_content:
                main_content = soup.find("article")

            if main_content:
                # Remove navigation, sidebar, and other non-content elements
                for unwanted in main_content.find_all(["nav", "aside", "footer", "header"]):
                    unwanted.decompose()

                # Remove script and style tags
                for script in main_content.find_all(["script", "style"]):
                    script.decompose()

                # Convert to markdown
                html_content = str(main_content)
                markdown_content = html_to_markdown(html_content, docs_url)

                # Extract and prioritize sections
                sections = extract_sections(markdown_content)
                if sections:
                    final_content = prioritize_sections(sections, max_bytes)
                # No sections found, use raw content with truncation
                elif len(markdown_content.encode("utf-8")) > max_bytes:
                    # Simple truncation
                    encoded = markdown_content.encode("utf-8")[:max_bytes]
                    # Handle potential multi-byte character splits
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
            else:
                # No main content found
                final_content = f"Documentation for {service_name} is available at {docs_url}"

            return {
                "service": service_name,
                "content": final_content,
                "size_bytes": len(final_content.encode("utf-8")),
                "source": "gcp_docs",
                "docs_url": docs_url,
                "truncated": len(final_content.encode("utf-8")) >= max_bytes,
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {
                    "service": service,
                    "content": "",
                    "error": "Service documentation not found",
                    "size_bytes": 0,
                    "source": None,
                }
            return {
                "service": service,
                "content": "",
                "error": f"GCP docs returned {exc.response.status_code}",
                "size_bytes": 0,
                "source": None,
            }
        except httpx.HTTPError as exc:
            return {
                "service": service,
                "content": "",
                "error": f"Failed to fetch docs: {exc}",
                "size_bytes": 0,
                "source": None,
            }
        except Exception as exc:
            return {
                "service": service,
                "content": "",
                "error": f"Failed to process docs: {exc!s}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def search_gcp_services(query: str, limit: int = 5) -> CallToolResult:
            """
            Search for GCP (Google Cloud Platform) services and documentation.

            USE THIS WHEN: You need to find Google Cloud services, APIs, or documentation for a specific GCP topic.

            BEST FOR: Discovering which GCP services exist for a use case or finding service documentation.
            Returns multiple matching services with names, descriptions, API endpoints, and docs URLs.

            Searches:
            1. Local service mapping (exact and partial matches)
            2. cloud.google.com website (fallback for specific queries)
            3. googleapis GitHub repository (API definitions)

            After finding a service, use:
            - fetch_gcp_service_docs() to get full documentation content
            - The docs_url with WebFetch for external documentation

            Note: GitHub API search (fallback) is limited to 60 requests/hour without GITHUB_TOKEN.

            Args:
                query: Service name or keywords (e.g., "storage", "vertex ai", "gke audit", "bigquery")
                limit: Maximum number of results (default 5)

            Returns:
                JSON with list of matching services including name, description, API endpoint, docs URL

            Example: search_gcp_services("vertex ai") → Finds Vertex AI service with docs links
            """
            result = await self._search_services(query, limit=limit)
            return serialize_response_with_meta(result)

        async def fetch_gcp_service_docs(service: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch actual documentation content for a GCP (Google Cloud Platform) service.

            USE THIS WHEN: You need detailed documentation, guides, tutorials, or API reference for a GCP service.

            BEST FOR: Getting complete documentation with setup instructions, usage examples, and API details.
            Better than using curl or WebFetch because it:
            - Automatically extracts relevant content from cloud.google.com
            - Converts HTML to clean Markdown format
            - Prioritizes important sections (Overview, Quickstart, API Reference)
            - Removes navigation, ads, and other non-content elements
            - Handles multi-word service names (e.g., "gke audit policy")

            Works with:
            - Exact service names (e.g., "Cloud Storage", "Compute Engine")
            - Common abbreviations (e.g., "GCS", "GKE", "BigQuery")
            - Multi-word queries (e.g., "gke audit policy configuration")

            Args:
                service: Service name or topic (e.g., "Cloud Storage", "vertex ai", "gke audit")
                max_bytes: Maximum content size, default 20KB (increase for comprehensive docs)

            Returns:
                JSON with documentation content, size, source URL, truncation status

            Example: fetch_gcp_service_docs("vertex ai") → Returns formatted documentation from cloud.google.com
            """
            result = await self._fetch_service_docs(service, max_bytes)
            return serialize_response_with_meta(result)

        tools = {"search_gcp_services": search_gcp_services}
        if is_fetch_enabled():
            tools["fetch_gcp_service_docs"] = fetch_gcp_service_docs

        return tools
