"""GitHub repository and code search provider."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..content_utils import convert_relative_urls
from ..utils import USER_AGENT, get_github_token, is_fetch_enabled, serialize_response_with_meta
from .base import BaseProvider, ProviderMetadata, ProviderResult


class GitHubProvider(BaseProvider):
    """Provider for GitHub repository and code search."""

    def get_metadata(self) -> ProviderMetadata:
        tool_names = ["github_repo_search", "github_code_search"]
        if is_fetch_enabled():
            tool_names.extend(
                [
                    "fetch_github_readme",
                    "list_repo_contents",
                    "get_file_content",
                    "get_repo_tree",
                    "get_commit_diff",
                    "list_github_packages",
                    "get_package_versions",
                ]
            )

        return ProviderMetadata(
            name="github",
            description="GitHub repository and code search, file browsing, and content fetching",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=["GITHUB_TOKEN", "GITHUB_AUTH"],
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """Search GitHub repos for library (used by aggregator)."""
        try:
            # Aggregator adds "python" suffix for language context
            data = await self._search_repos(f"{library} python", limit=limit)
            return ProviderResult(success=True, data=data, provider_name="github")
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200] if exc.response is not None else ""
            error_msg = f"GitHub returned {exc.response.status_code} {detail}"
            return ProviderResult(success=False, error=error_msg, provider_name="github")
        except httpx.HTTPError as exc:
            error_msg = f"GitHub request failed: {exc}"
            return ProviderResult(success=False, error=error_msg, provider_name="github")

    async def _search_repos(
        self, query: str, limit: int = 5, language: str | None = "Python"
    ) -> list[dict[str, Any]]:
        """Query GitHub's repository search API."""
        headers = self._get_headers()

        params = {"q": query, "per_page": str(limit)}
        if language:
            params["q"] = f"{query} language:{language}"

        async with await self._http_client() as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()

        repos: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            repos.append(
                {
                    "name": item.get("full_name"),
                    "description": item.get("description") or "",
                    "stars": item.get("stargazers_count", 0),
                    "url": item.get("html_url"),
                    "default_branch": item.get("default_branch"),
                }
            )
            if len(repos) >= limit:
                break
        return repos

    async def _search_code(
        self, query: str, repo: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search code on GitHub; optionally scoping to a repository."""
        headers = self._get_headers()

        search_query = query
        if repo:
            search_query = f"{query} repo:{repo}"

        params = {"q": search_query, "per_page": str(limit)}
        async with await self._http_client() as client:
            resp = await client.get(
                "https://api.github.com/search/code",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()

        code_hits: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            code_hits.append(
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "repository": item.get("repository", {}).get("full_name"),
                    "url": item.get("html_url"),
                }
            )
            if len(code_hits) >= limit:
                break
        return code_hits

    def _get_headers(self) -> dict[str, str]:
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

    async def _fetch_github_readme(
        self, owner: str, repo: str, max_bytes: int = 20480
    ) -> dict[str, Any]:
        """
        Fetch README from GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name
            max_bytes: Maximum content size

        Returns:
            Dict with content, size, source info
        """
        try:
            headers = self._get_headers()
            url = f"https://api.github.com/repos/{owner}/{repo}/readme"

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Decode base64 content
            content = base64.b64decode(data["content"]).decode("utf-8")

            # Convert relative URLs to absolute
            # Use the blob URL for the specific branch/path
            data.get("name", "README.md")
            readme_path = data.get("path", "")
            default_branch = "main"  # Could be fetched from repo metadata if needed

            base_url = f"https://github.com/{owner}/{repo}/blob/{default_branch}"
            if readme_path and "/" in readme_path:
                # If README is in a subdirectory
                dir_path = "/".join(readme_path.split("/")[:-1])
                base_url = f"{base_url}/{dir_path}"

            content = convert_relative_urls(content, base_url)

            # Truncate if needed
            if len(content.encode("utf-8")) > max_bytes:
                # Simple truncation for now - could use smart_truncate
                encoded = content.encode("utf-8")[:max_bytes]
                # Handle potential multi-byte character splits
                while len(encoded) > 0:
                    try:
                        content = encoded.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        encoded = encoded[:-1]
                truncated = True
            else:
                truncated = False

            return {
                "repository": f"{owner}/{repo}",
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "source": "github_readme",
                "readme_path": readme_path,
                "truncated": truncated,
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "content": "",
                "error": f"GitHub returned {exc.response.status_code}",
                "size_bytes": 0,
                "source": None,
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "content": "",
                "error": f"Failed to fetch README: {exc!s}",
                "size_bytes": 0,
                "source": None,
            }

    async def _list_repo_contents(self, owner: str, repo: str, path: str = "") -> dict[str, Any]:
        """
        List contents of a directory in a GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to directory (empty string for root)

        Returns:
            Dict with list of files and directories
        """
        try:
            headers = self._get_headers()
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Handle single file vs directory
            if isinstance(data, dict):
                # Single file was requested
                items = [data]
            else:
                items = data

            contents = []
            for item in items:
                contents.append(
                    {
                        "name": item.get("name"),
                        "path": item.get("path"),
                        "type": item.get("type"),  # "file" or "dir"
                        "size": item.get("size"),
                        "sha": item.get("sha"),
                        "url": item.get("html_url"),
                        "download_url": item.get("download_url"),
                    }
                )

            return {
                "repository": f"{owner}/{repo}",
                "path": path or "/",
                "contents": contents,
                "count": len(contents),
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "path": path,
                "contents": [],
                "error": f"GitHub returned {exc.response.status_code}",
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "path": path,
                "contents": [],
                "error": f"Failed to list contents: {exc!s}",
            }

    async def _get_file_content(
        self, owner: str, repo: str, path: str, max_bytes: int = 102400
    ) -> dict[str, Any]:
        """
        Get content of a specific file from a GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to file
            max_bytes: Maximum content size (default 100KB)

        Returns:
            Dict with file content and metadata
        """
        try:
            headers = self._get_headers()
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Check if it's a file
            if data.get("type") != "file":
                return {
                    "repository": f"{owner}/{repo}",
                    "path": path,
                    "content": "",
                    "error": f"Path is a {data.get('type')}, not a file",
                }

            # Decode base64 content
            try:
                content = base64.b64decode(data["content"]).decode("utf-8")
            except UnicodeDecodeError:
                # Binary file
                return {
                    "repository": f"{owner}/{repo}",
                    "path": path,
                    "content": "",
                    "error": "File appears to be binary",
                    "size_bytes": data.get("size", 0),
                    "encoding": data.get("encoding"),
                }

            # Truncate if needed
            truncated = False
            if len(content.encode("utf-8")) > max_bytes:
                encoded = content.encode("utf-8")[:max_bytes]
                while len(encoded) > 0:
                    try:
                        content = encoded.decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        encoded = encoded[:-1]
                truncated = True

            return {
                "repository": f"{owner}/{repo}",
                "path": path,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
                "truncated": truncated,
                "sha": data.get("sha"),
                "url": data.get("html_url"),
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "path": path,
                "content": "",
                "error": f"GitHub returned {exc.response.status_code}",
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "path": path,
                "content": "",
                "error": f"Failed to get file content: {exc!s}",
            }

    async def _get_repo_tree(
        self, owner: str, repo: str, recursive: bool = False, max_items: int = 1000
    ) -> dict[str, Any]:
        """
        Get the full file tree of a GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name
            recursive: Whether to get full tree recursively
            max_items: Maximum number of items to return

        Returns:
            Dict with file tree structure
        """
        try:
            headers = self._get_headers()

            # First get the default branch
            repo_url = f"https://api.github.com/repos/{owner}/{repo}"
            async with await self._http_client() as client:
                repo_resp = await client.get(repo_url, headers=headers)
                repo_resp.raise_for_status()
                repo_data = repo_resp.json()
                default_branch = repo_data.get("default_branch", "main")

            # Get the tree
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}"
            if recursive:
                tree_url += "?recursive=1"

            async with await self._http_client() as client:
                resp = await client.get(tree_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            tree_items = data.get("tree", [])[:max_items]

            tree = []
            for item in tree_items:
                tree.append(
                    {
                        "path": item.get("path"),
                        "type": item.get("type"),  # "blob" (file) or "tree" (dir)
                        "size": item.get("size"),
                        "sha": item.get("sha"),
                        "url": item.get("url"),
                    }
                )

            return {
                "repository": f"{owner}/{repo}",
                "branch": default_branch,
                "tree": tree,
                "count": len(tree),
                "truncated": data.get("truncated", False) or len(tree_items) >= max_items,
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "tree": [],
                "error": f"GitHub returned {exc.response.status_code}",
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "tree": [],
                "error": f"Failed to get repository tree: {exc!s}",
            }

    async def _get_commit_diff(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        """
        Get the diff between two commits.

        Args:
            owner: Repository owner
            repo: Repository name
            base: Base commit/branch/tag
            head: Head commit/branch/tag

        Returns:
            Dict with diff content
        """
        try:
            headers = self._get_headers()
            # Request raw diff format
            headers["Accept"] = "application/vnd.github.diff"

            url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"

            async with await self._http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                diff_content = resp.text

            return {
                "repository": f"{owner}/{repo}",
                "base": base,
                "head": head,
                "diff": diff_content,
                "size_bytes": len(diff_content.encode("utf-8")),
            }

        except httpx.HTTPStatusError as exc:
            return {
                "repository": f"{owner}/{repo}",
                "base": base,
                "head": head,
                "diff": "",
                "error": f"GitHub returned {exc.response.status_code}",
            }
        except Exception as exc:
            return {
                "repository": f"{owner}/{repo}",
                "base": base,
                "head": head,
                "diff": "",
                "error": f"Failed to get diff: {exc!s}",
            }

    async def _list_github_packages(
        self, owner: str, package_type: str = "container"
    ) -> list[dict[str, Any]]:
        """
        List packages for a user or organization.

        Args:
            owner: User or organization name
            package_type: Type of package (container, npm, maven, rubygems, docker, nuget)
                          Note: "docker" is legacy, "container" is GHCR.

        Returns:
            List of packages
        """
        try:
            headers = self._get_headers()

            # API endpoint differs for users vs orgs, but we don't know which one 'owner' is easily.
            # We can try orgs first, then users if it fails, or rely on the caller knowing.
            # However, the public API structure usually requires knowing if it's a user or org.
            # Strategy: Try /users/{username}/packages first, if 404 try /orgs/{org}/packages

            endpoints = [
                f"https://api.github.com/users/{owner}/packages?package_type={package_type}",
                f"https://api.github.com/orgs/{owner}/packages?package_type={package_type}",
            ]

            data = []
            error = None

            async with await self._http_client() as client:
                for url in endpoints:
                    try:
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            error = None
                            break
                        elif resp.status_code == 404:
                            # Not found, try next endpoint
                            continue
                        else:
                            resp.raise_for_status()
                    except httpx.HTTPError as exc:
                        error = exc
                        continue

                if not data and error:
                    # If we tried both and failed, raise the last error
                    raise error or Exception(f"Could not find packages for {owner}")

            packages = []
            for item in data:
                packages.append(
                    {
                        "name": item.get("name"),
                        "package_type": item.get("package_type"),
                        "owner": item.get("owner", {}).get("login"),
                        "repository": item.get("repository", {}).get("full_name"),
                        "url": item.get("html_url"),
                        "version_count": item.get("version_count", 0),
                        "visibility": item.get("visibility"),
                    }
                )

            return packages

        except Exception as exc:
            # If completely failed (e.g. 404 on both), return empty list or re-raise?
            # For now, let's catch it in the public method wrapper
            raise exc

    async def _get_package_versions(
        self, owner: str, package_type: str, package_name: str
    ) -> list[dict[str, Any]]:
        """
        Get versions of a specific package.
        """
        try:
            headers = self._get_headers()

            # Similar strategy for orgs vs users
            # /users/{username}/packages/{package_type}/{package_name}/versions
            # /orgs/{org}/packages/{package_type}/{package_name}/versions

            endpoints = [
                f"https://api.github.com/users/{owner}/packages/{package_type}/{package_name}/versions",
                f"https://api.github.com/orgs/{owner}/packages/{package_type}/{package_name}/versions",
            ]

            data = []
            error = None

            async with await self._http_client() as client:
                for url in endpoints:
                    try:
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            error = None
                            break
                        elif resp.status_code == 404:
                            continue
                        else:
                            resp.raise_for_status()
                    except httpx.HTTPError as exc:
                        error = exc
                        continue

                if not data and error:
                    raise error or Exception(f"Could not find versions for {package_name}")

            versions = []
            for item in data:
                metadata = item.get("metadata", {})
                container_metadata = metadata.get("container", {})
                tags = container_metadata.get("tags", [])

                versions.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),  # SHA usually
                        "url": item.get("html_url"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                        "tags": tags,
                    }
                )

            return versions

        except Exception as exc:
            raise exc

    def get_tools(self) -> dict[str, Callable]:
        """Return MCP tool functions."""

        async def github_repo_search(
            query: str, limit: int = 5, language: str | None = "Python"
        ) -> CallToolResult:
            """
            Search for GitHub repositories by keyword or topic.

            USE THIS WHEN: You need to find repositories for a library, framework, or topic.

            BEST FOR: Discovering which repository contains a specific project.
            Returns repository names, descriptions, stars, and URLs - but NOT the code itself.

            To explore code after finding a repo, use:
            - get_repo_tree() to see all files
            - list_repo_contents() to browse directories
            - get_file_content() to read specific files

            Args:
                query: Search keywords (e.g., "machine learning", "web framework")
                limit: Maximum number of results (default 5)
                language: Filter by programming language (default "Python")

            Example: github_repo_search("requests") → Finds psf/requests repository
            """
            result = await self._search_repos(query, limit=limit, language=language)
            return serialize_response_with_meta(result)

        async def github_code_search(
            query: str, repo: str | None = None, limit: int = 5
        ) -> CallToolResult:
            """
            Search for code snippets across GitHub or within a specific repository.

            USE THIS WHEN: You need to find code examples, function definitions, or usage patterns.

            RETURNS: File paths and locations where code was found - NOT the actual file contents.
            To read the files, use get_file_content() with the returned paths.

            NOTE: Requires authentication - rate limited without GITHUB_TOKEN.

            Args:
                query: Code search query (e.g., "def parse_args", "class HTTPClient")
                repo: Optional repository filter in "owner/repo" format
                limit: Maximum number of results (default 5)

            Example: github_code_search("async def fetch", repo="psf/requests")
            """
            result = await self._search_code(query, repo=repo, limit=limit)
            return serialize_response_with_meta(result)

        async def list_github_packages(
            owner: str, package_type: str = "container"
        ) -> CallToolResult:
            """
            List packages (including GHCR images) for a GitHub user or organization.

            USE THIS WHEN: You want to find Docker images or other packages hosted on GitHub for a specific user/org.
            Note: GitHub does not support global package search; you must provide an owner.

            Args:
                owner: GitHub username or organization name (e.g. "github", "octocat")
                package_type: Type of package to list. Defaults to "container" (GHCR).
                              Options: "container", "npm", "maven", "rubygems", "nuget", "docker" (legacy)

            Returns:
                JSON list of packages with metadata (name, repository, version count, etc.)
            """
            try:
                data = await self._list_github_packages(owner, package_type)
                result = {
                    "owner": owner,
                    "package_type": package_type,
                    "packages": data,
                    "count": len(data),
                }
                return serialize_response_with_meta(result)
            except Exception as exc:
                return serialize_response_with_meta(
                    {"owner": owner, "error": f"Failed to list packages: {exc!s}"}
                )

        async def get_package_versions(
            owner: str, package_type: str, package_name: str
        ) -> CallToolResult:
            """
            Get versions for a specific GitHub package.

            USE THIS WHEN: You found a package using list_github_packages and want to see available tags/versions.

            Args:
                owner: GitHub username or organization name
                package_type: Type of package (e.g., "container")
                package_name: Name of the package (e.g., "rtfd")

            Returns:
                JSON list of versions/tags.
            """
            try:
                data = await self._get_package_versions(owner, package_type, package_name)
                result = {
                    "owner": owner,
                    "package_name": package_name,
                    "versions": data,
                    "count": len(data),
                }
                return serialize_response_with_meta(result)
            except Exception as exc:
                return serialize_response_with_meta(
                    {
                        "owner": owner,
                        "package_name": package_name,
                        "error": f"Failed to get versions: {exc!s}",
                    }
                )

        async def fetch_github_readme(repo: str, max_bytes: int = 20480) -> CallToolResult:
            """
            Fetch README file from a GitHub repository.

            USE THIS WHEN: You need the project overview, quick start, or basic documentation.

            BEST FOR: Getting a high-level understanding of a project.
            The README typically contains installation, usage examples, and project description.

            For deeper code exploration, use:
            - get_repo_tree() to see the complete file structure
            - get_file_content() to read specific source files

            Args:
                repo: Repository in "owner/repo" format (e.g., "psf/requests")
                max_bytes: Maximum content size, default 20KB

            Returns: JSON with README content, size, and metadata

            Example: fetch_github_readme("psf/requests") → Returns the requests README
            """
            # Parse owner/repo format
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "content": "",
                    "error": "Invalid repo format. Use 'owner/repo'",
                    "size_bytes": 0,
                    "source": None,
                }
                return serialize_response_with_meta(error_result)

            owner, repo_name = parts
            result = await self._fetch_github_readme(owner, repo_name, max_bytes)
            return serialize_response_with_meta(result)

        async def list_repo_contents(repo: str, path: str = "") -> CallToolResult:
            """
            List contents of a directory in a GitHub repository.

            USE THIS WHEN: You need to browse or explore the structure of a repository directory.

            BEST FOR: Discovering what files and folders exist in a specific location.
            Returns names, paths, types (file/dir), sizes for each item.

            Common workflow:
            1. Use github_repo_search() to find the repository
            2. Use get_repo_tree() to see the overall structure
            3. Use list_repo_contents() to browse specific directories
            4. Use get_file_content() to read individual files

            Args:
                repo: Repository in format "owner/repo" (e.g., "psf/requests")
                path: Path to directory (empty string for root, e.g., "src/utils")

            Returns:
                JSON with list of files and directories with metadata

            Example: list_repo_contents("psf/requests", "requests") → Lists files in requests/ directory
            """
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "path": path,
                    "contents": [],
                    "error": "Invalid repo format. Use 'owner/repo'",
                }
                return serialize_response_with_meta(error_result)

            owner, repo_name = parts
            result = await self._list_repo_contents(owner, repo_name, path)
            return serialize_response_with_meta(result)

        async def get_file_content(repo: str, path: str, max_bytes: int = 102400) -> CallToolResult:
            """
            Get content of a specific file from a GitHub repository.

            USE THIS WHEN: You need to read the actual source code or contents of a specific file.

            BEST FOR: Examining implementation details, understanding how code works, or reading configuration files.
            Returns the full file content (UTF-8 text only, binary files are rejected).

            Automatically handles:
            - Base64 decoding from GitHub API
            - UTF-8 conversion with safe truncation
            - Binary file detection

            Args:
                repo: Repository in format "owner/repo" (e.g., "psf/requests")
                path: Path to file (e.g., "requests/api.py")
                max_bytes: Maximum content size (default 100KB, increase for large files)

            Returns:
                JSON with file content, size, truncation status, and metadata

            Example: get_file_content("psf/requests", "requests/api.py") → Returns source code of api.py
            """
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "path": path,
                    "content": "",
                    "error": "Invalid repo format. Use 'owner/repo'",
                }
                return serialize_response_with_meta(error_result)

            owner, repo_name = parts
            result = await self._get_file_content(owner, repo_name, path, max_bytes)
            return serialize_response_with_meta(result)

        async def get_repo_tree(
            repo: str, recursive: bool = False, max_items: int = 1000
        ) -> CallToolResult:
            """
            Get the full file tree of a GitHub repository.

            USE THIS WHEN: You need to see the overall structure and organization of a repository.

            BEST FOR: Understanding project layout, finding specific files, or getting a complete directory listing.
            Returns all file paths, types (file/directory), and sizes in a single call.

            Use recursive=True for complete tree (all files in all subdirectories).
            Use recursive=False for just top-level overview (faster, less data).

            After getting the tree, use:
            - get_file_content() to read specific files you identified
            - list_repo_contents() to browse specific directories in detail

            Args:
                repo: Repository in format "owner/repo" (e.g., "psf/requests")
                recursive: Whether to get full tree recursively (default False)
                max_items: Maximum number of items to return (default 1000)

            Returns:
                JSON with complete file tree structure, branch, and count

            Example: get_repo_tree("psf/requests", recursive=True) → Returns complete file listing
            """
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "tree": [],
                    "error": "Invalid repo format. Use 'owner/repo'",
                }
                return serialize_response_with_meta(error_result)

            owner, repo_name = parts
            result = await self._get_repo_tree(owner, repo_name, recursive, max_items)
            return serialize_response_with_meta(result)

        async def get_commit_diff(repo: str, base: str, head: str) -> CallToolResult:
            """
            Get the diff between two commits, branches, or tags in a GitHub repository.

            USE THIS WHEN: You need to see what changed between two versions of code.

            BEST FOR: Analyzing changes, reviewing pull requests (by comparing branches), or checking version differences.
            Returns the raw git diff output.

            Args:
                repo: Repository in format "owner/repo" (e.g., "psf/requests")
                base: Base commit SHA, branch name, or tag (e.g., "main", "v1.0.0", "a1b2c3d")
                head: Head commit SHA, branch name, or tag (e.g., "feature-branch", "v1.1.0", "e5f6g7h")

            Returns:
                JSON with the raw git diff content.

            Example: get_commit_diff("psf/requests", "v2.28.0", "v2.28.1") → Returns diff between versions
            """
            parts = repo.split("/", 1)
            if len(parts) != 2:
                error_result = {
                    "repository": repo,
                    "base": base,
                    "head": head,
                    "diff": "",
                    "error": "Invalid repo format. Use 'owner/repo'",
                }
                return serialize_response_with_meta(error_result)

            owner, repo_name = parts
            result = await self._get_commit_diff(owner, repo_name, base, head)
            return serialize_response_with_meta(result)

        tools = {
            "github_repo_search": github_repo_search,
            "github_code_search": github_code_search,
            "list_github_packages": list_github_packages,
            "get_package_versions": get_package_versions,
        }
        if is_fetch_enabled():
            tools["fetch_github_readme"] = fetch_github_readme
            tools["list_repo_contents"] = list_repo_contents
            tools["get_file_content"] = get_file_content
            tools["get_repo_tree"] = get_repo_tree
            tools["get_commit_diff"] = get_commit_diff

        return tools
