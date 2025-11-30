"""DockerHub Docker image metadata provider."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import httpx
from mcp.types import CallToolResult

from ..utils import serialize_response_with_meta, is_fetch_enabled
from .base import BaseProvider, ProviderMetadata, ProviderResult


class DockerHubProvider(BaseProvider):
    """Provider for DockerHub Docker image metadata and search."""

    DOCKERHUB_API_URL = "https://hub.docker.com/v2"

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["search_docker_images", "docker_image_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_docker_image_docs")

        return ProviderMetadata(
            name="dockerhub",
            description="DockerHub Docker image search and metadata",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=False,  # DockerHub search is image-centric, not lib-doc
            required_env_vars=[],
            optional_env_vars=[],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Not used for DockerHub (images are searched via search_docker_images)."""
        return ProviderResult(success=False, error=None, provider_name="dockerhub")

    async def _search_images(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search for Docker images on DockerHub.

        Args:
            query: Search query (image name)
            limit: Maximum number of results to return

        Returns:
            Dict with search results
        """
        try:
            url = f"{self.DOCKERHUB_API_URL}/search/repositories/"
            params = {"query": query, "page_size": limit}

            async with await self._http_client() as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()

            # Transform results
            results = []
            for item in payload.get("results", []):
                repo_name = item.get("repo_name", "")
                repo_owner = item.get("repo_owner", "")
                # For official images, repo_owner is empty, show as library/name
                display_name = f"{repo_owner}/{repo_name}" if repo_owner else f"library/{repo_name}"

                results.append({
                    "name": repo_name,
                    "owner": repo_owner or "library",
                    "description": item.get("short_description", ""),
                    "star_count": item.get("star_count", 0),
                    "pull_count": item.get("pull_count", 0),
                    "is_official": item.get("is_official", False),
                    "url": f"https://hub.docker.com/r/{display_name}",
                })

            return {
                "query": query,
                "count": len(results),
                "results": results,
            }

        except httpx.HTTPStatusError as exc:
            return {
                "query": query,
                "error": f"DockerHub returned {exc.response.status_code}",
                "results": [],
            }
        except httpx.HTTPError as exc:
            return {
                "query": query,
                "error": f"DockerHub request failed: {exc}",
                "results": [],
            }
        except Exception as exc:
            return {
                "query": query,
                "error": f"Failed to search images: {str(exc)}",
                "results": [],
            }

    async def _fetch_image_metadata(
        self, image: str
    ) -> Dict[str, Any]:
        """Fetch detailed metadata for a Docker image.

        Args:
            image: Image name (can be 'namespace/name' or just 'name' for library)

        Returns:
            Dict with image metadata
        """
        try:
            # Handle library images (e.g., 'nginx' -> 'library/nginx')
            if "/" not in image:
                repo_path = f"library/{image}"
            else:
                repo_path = image

            url = f"{self.DOCKERHUB_API_URL}/repositories/{repo_path}/"

            async with await self._http_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            return {
                "name": data.get("name"),
                "namespace": data.get("namespace"),
                "full_name": data.get("full_name", f"{data.get('namespace')}/{data.get('name')}"),
                "description": data.get("description", ""),
                "readme": data.get("readme", ""),  # Full readme text if available
                "last_updated": data.get("last_updated"),
                "star_count": data.get("star_count", 0),
                "pull_count": data.get("pull_count", 0),
                "is_official": data.get("is_official", False),
                "is_private": data.get("is_private", False),
                "repository_type": data.get("repository_type"),
                "url": f"https://hub.docker.com/r/{repo_path}",
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {
                    "image": image,
                    "error": "Image not found on DockerHub",
                }
            return {
                "image": image,
                "error": f"DockerHub returned {exc.response.status_code}",
            }
        except httpx.HTTPError as exc:
            return {
                "image": image,
                "error": f"DockerHub request failed: {exc}",
            }
        except Exception as exc:
            return {
                "image": image,
                "error": f"Failed to fetch metadata: {str(exc)}",
            }

    async def _fetch_image_docs(
        self, image: str, max_bytes: int = 20480
    ) -> Dict[str, Any]:
        """Fetch documentation for a Docker image.

        Args:
            image: Image name (e.g., 'nginx', 'postgres', 'myuser/myimage')
            max_bytes: Maximum content size in bytes

        Returns:
            Dict with documentation content
        """
        try:
            metadata = await self._fetch_image_metadata(image)

            # Check if we got an error
            if "error" in metadata:
                return {
                    "image": image,
                    "content": "",
                    "error": metadata["error"],
                    "size_bytes": 0,
                    "source": None,
                }

            # Extract readme if available
            readme = metadata.get("readme", "")
            description = metadata.get("description", "")

            # Combine description and readme
            content = ""
            if description:
                content = f"## Description\n\n{description}\n\n"
            if readme:
                content += f"## README\n\n{readme}"
            elif not description:
                content = "No documentation available for this image."

            # Truncate if necessary
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > max_bytes:
                content = content[:max_bytes]
                truncated = True
            else:
                truncated = False

            return {
                "image": image,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "source": "dockerhub",
                "truncated": truncated,
            }

        except Exception as exc:
            return {
                "image": image,
                "content": "",
                "error": f"Failed to fetch docs: {str(exc)}",
                "size_bytes": 0,
                "source": None,
            }

    def get_tools(self) -> Dict[str, Callable]:
        """Return MCP tool functions."""

        async def search_docker_images(query: str, limit: int = 5) -> CallToolResult:
            """Search for Docker images on DockerHub.

            Args:
                query: Search query (image name or keyword)
                limit: Maximum number of results to return (default 5)

            Returns:
                List of matching Docker images with metadata
            """
            result = await self._search_images(query, limit)
            return serialize_response_with_meta(result)

        async def docker_image_metadata(image: str) -> CallToolResult:
            """Retrieve DockerHub Docker image metadata.

            Args:
                image: Docker image name (e.g., 'nginx', 'postgres', 'user/image')

            Returns:
                Image metadata including stars, pulls, last update, description
            """
            result = await self._fetch_image_metadata(image)
            return serialize_response_with_meta(result)

        async def fetch_docker_image_docs(
            image: str, max_bytes: int = 20480
        ) -> CallToolResult:
            """Fetch Docker image documentation from DockerHub.

            Returns description and README content for a Docker image.
            Useful for understanding what an image does and how to use it.

            Args:
                image: Docker image name (e.g., 'nginx', 'postgres', 'user/image')
                max_bytes: Maximum content size (default ~20KB)

            Returns:
                JSON with image documentation content
            """
            result = await self._fetch_image_docs(image, max_bytes)
            return serialize_response_with_meta(result)

        tools = {
            "search_docker_images": search_docker_images,
            "docker_image_metadata": docker_image_metadata,
        }
        if is_fetch_enabled():
            tools["fetch_docker_image_docs"] = fetch_docker_image_docs

        return tools
