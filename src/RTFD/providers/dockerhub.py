"""DockerHub Docker image metadata provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..utils import is_fetch_enabled, serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class DockerHubProvider(BaseProvider):
    """Provider for DockerHub Docker image metadata and search."""

    DOCKERHUB_API_URL = "https://hub.docker.com/v2"

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["search_docker_images", "docker_image_metadata"]
        if is_fetch_enabled():
            tool_names.append("fetch_docker_image_docs")
            tool_names.append("fetch_dockerfile")

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

    async def _search_images(self, query: str, limit: int = 5) -> dict[str, Any]:
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

                results.append(
                    {
                        "name": repo_name,
                        "owner": repo_owner or "library",
                        "description": item.get("short_description", ""),
                        "star_count": item.get("star_count", 0),
                        "pull_count": item.get("pull_count", 0),
                        "is_official": item.get("is_official", False),
                        "url": f"https://hub.docker.com/r/{display_name}",
                    }
                )

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
                "error": f"Failed to search images: {exc!s}",
                "results": [],
            }

    async def _fetch_image_metadata(self, image: str) -> dict[str, Any]:
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
                "error": f"Failed to fetch metadata: {exc!s}",
            }

    async def _fetch_image_docs(self, image: str, max_bytes: int = 20480) -> dict[str, Any]:
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
                "error": f"Failed to fetch docs: {exc!s}",
                "size_bytes": 0,
                "source": None,
            }

    async def _fetch_dockerfile(self, image: str) -> dict[str, Any]:
        """Fetch Dockerfile for an image by parsing its description for GitHub links.

        Args:
            image: Image name (e.g., 'nginx', 'python')

        Returns:
            Dict with Dockerfile content or error
        """
        import re

        try:
            # 1. Get image metadata to find the description
            metadata = await self._fetch_image_metadata(image)
            if "error" in metadata:
                return {
                    "image": image,
                    "error": metadata["error"],
                    "source": None,
                }

            # 2. Get the full description (README)
            # Note: _fetch_image_metadata might not return full_description if it uses the summary endpoint,
            # but let's check if we need to make a separate call or if we can rely on what we have.
            # The previous investigation showed we need to hit the repository endpoint which _fetch_image_metadata does.
            # However, the 'readme' field in _fetch_image_metadata comes from 'readme' key in JSON.
            # Let's verify if 'full_description' is available in the payload of _fetch_image_metadata.
            # Looking at _fetch_image_metadata implementation:
            # url = f"{self.DOCKERHUB_API_URL}/repositories/{repo_path}/"
            # This endpoint returns 'full_description' usually.
            # But _fetch_image_metadata returns a dict with specific keys.
            # We need to access the raw description.

            # Let's re-fetch to be sure we get the full description text to parse
            if "/" not in image:
                repo_path = f"library/{image}"
            else:
                repo_path = image

            url = f"{self.DOCKERHUB_API_URL}/repositories/{repo_path}/"

            async with await self._http_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            full_desc = data.get("full_description", "")

            # 3. Find GitHub Dockerfile links
            # Pattern: https://github.com/[owner]/[repo]/blob/[ref]/[path/to/]Dockerfile
            # We want to capture the whole URL
            github_pattern = r"https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/blob/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*/Dockerfile"

            matches = re.findall(github_pattern, full_desc)

            if not matches:
                return {
                    "image": image,
                    "error": "No GitHub Dockerfile link found in image description",
                    "source": "dockerhub_description",
                }

            # Use the first match (often the 'latest' or most prominent one)
            # Ideally we'd match against a specific tag if provided, but for now we take the first one.
            dockerfile_url = matches[0]

            # 4. Convert to raw GitHub URL
            # From: https://github.com/user/repo/blob/ref/path/Dockerfile
            # To:   https://raw.githubusercontent.com/user/repo/ref/path/Dockerfile

            raw_url = dockerfile_url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )

            # 5. Fetch the Dockerfile
            async with await self._http_client() as client:
                resp = await client.get(raw_url)
                resp.raise_for_status()
                content = resp.text

            return {
                "image": image,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "source": raw_url,
                "found_in_description": True,
            }

        except Exception as exc:
            return {
                "image": image,
                "error": f"Failed to fetch Dockerfile: {exc!s}",
                "source": None,
            }

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def search_docker_images(query: str, limit: int = 5) -> CallToolResult:
            """
            Search for Docker images on DockerHub by name or keywords.

            USE THIS WHEN: You need to find Docker container images for a specific service, application, or technology.

            BEST FOR: Discovering official and community Docker images.
            Returns multiple matching images with names, descriptions, star counts, pull counts, and whether they're official.

            After finding an image, use:
            - docker_image_metadata() for detailed information
            - fetch_docker_image_docs() for README and usage instructions
            - fetch_dockerfile() to see how the image is built

            Args:
                query: Search query (e.g., "nginx", "postgres", "machine learning", "python")
                limit: Maximum number of results (default 5)

            Returns:
                JSON with list of matching images including name, description, stars, pulls, official status

            Example: search_docker_images("postgres") → Finds official postgres image and alternatives
            """
            result = await self._search_images(query, limit)
            return serialize_response_with_meta(result)

        async def docker_image_metadata(image: str) -> CallToolResult:
            """
            Get detailed metadata for a specific Docker image from DockerHub.

            USE THIS WHEN: You need comprehensive information about a Docker image (stats, description, tags).

            RETURNS: Image metadata including popularity metrics and description.
            Does NOT include full README documentation.

            The response includes:
            - Image name, namespace, description
            - Star count (popularity)
            - Pull count (total downloads)
            - Last updated timestamp
            - Official/community status

            Args:
                image: Docker image name (e.g., "nginx", "postgres", "username/custom-image")

            Returns:
                JSON with comprehensive image metadata

            Example: docker_image_metadata("nginx") → Returns stars, pulls, description for nginx image
            """
            result = await self._fetch_image_metadata(image)
            return serialize_response_with_meta(result)

        async def fetch_docker_image_docs(image: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch actual Docker image documentation and README from DockerHub.

            USE THIS WHEN: You need usage instructions, environment variables, volume mounts, or examples.

            BEST FOR: Understanding how to use a Docker image and configure it properly.
            Better than using curl or WebFetch because it:
            - Extracts README content from DockerHub
            - Includes image description and key details
            - Formats content in readable Markdown
            - Prioritizes important sections (Usage, Environment Variables, Examples)

            Typical content includes:
            - How to run the container
            - Available environment variables
            - Volume mount points
            - Port configurations
            - Usage examples and docker-compose snippets

            Args:
                image: Docker image name (e.g., "nginx", "postgres", "redis")
                max_bytes: Maximum content size, default 20KB (increase for detailed docs)

            Returns:
                JSON with README content, size, and source info

            Example: fetch_docker_image_docs("nginx") → Returns README with usage instructions
            """
            result = await self._fetch_image_docs(image, max_bytes)
            return serialize_response_with_meta(result)

        async def fetch_dockerfile(image: str) -> CallToolResult:
            """
            Fetch the actual Dockerfile used to build a Docker image.

            USE THIS WHEN: You need to see exactly how an image is built (base image, installed packages, configuration).

            BEST FOR: Understanding image composition, security analysis, or learning how to build similar images.
            Attempts to find Dockerfile link in DockerHub description and fetches from source (usually GitHub).

            Useful for:
            - Seeing what base image is used
            - Identifying installed packages and dependencies
            - Understanding build process and optimizations
            - Security auditing (what's included in the image)
            - Learning Dockerfile best practices from official images

            Note: Not all images have publicly accessible Dockerfiles. Many official images do.

            Args:
                image: Docker image name (e.g., "nginx", "python", "postgres")

            Returns:
                JSON with Dockerfile content, source URL, and metadata (or error if not found)

            Example: fetch_dockerfile("nginx") → Returns Dockerfile from nginx GitHub repository
            """
            result = await self._fetch_dockerfile(image)
            return serialize_response_with_meta(result)

        tools = {
            "search_docker_images": search_docker_images,
            "docker_image_metadata": docker_image_metadata,
        }
        if is_fetch_enabled():
            tools["fetch_docker_image_docs"] = fetch_docker_image_docs
            tools["fetch_dockerfile"] = fetch_dockerfile

        return tools
