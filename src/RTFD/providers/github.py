"""GitHub repository and code search provider."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

import httpx
from mcp.types import CallToolResult

from ..content_utils import convert_relative_urls
from ..utils import (
    USER_AGENT,
    chunk_and_serialize_response,
    get_github_token,
    is_fetch_enabled,
    safe_json_loads,
    serialize_response_with_meta,
)
from .base import BaseProvider, ProviderMetadata, ProviderResult, ToolTierInfo


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

        # Tool tier classification for defer_loading recommendations
        tool_tiers = {
            "github_repo_search": ToolTierInfo(tier=1, defer_recommended=False, category="search"),
            "github_code_search": ToolTierInfo(tier=2, defer_recommended=True, category="search"),
            "fetch_github_readme": ToolTierInfo(tier=3, defer_recommended=True, category="fetch"),
            "list_repo_contents": ToolTierInfo(tier=3, defer_recommended=True, category="fetch"),
            "get_file_content": ToolTierInfo(tier=3, defer_recommended=True, category="fetch"),
            "get_repo_tree": ToolTierInfo(tier=3, defer_recommended=True, category="fetch"),
            "get_commit_diff": ToolTierInfo(tier=4, defer_recommended=True, category="fetch"),
            "list_github_packages": ToolTierInfo(tier=5, defer_recommended=True, category="fetch"),
            "get_package_versions": ToolTierInfo(tier=5, defer_recommended=True, category="fetch"),
        }

        return ProviderMetadata(
            name="github",
            description="GitHub repository and code search, file browsing, and content fetching",
            expose_as_tool=True,
            tool_names=tool_names,
            supports_library_search=True,
            required_env_vars=[],
            optional_env_vars=["GITHUB_TOKEN", "GITHUB_AUTH"],
            tool_tiers=tool_tiers,
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
            payload = safe_json_loads(resp.text)

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
            payload = safe_json_loads(resp.text)

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
                data = safe_json_loads(resp.text)

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
                data = safe_json_loads(resp.text)

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
                data = safe_json_loads(resp.text)

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
                repo_data = safe_json_loads(repo_resp.text)
                default_branch = repo_data.get("default_branch", "main")

            # Get the tree
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}"
            if recursive:
                tree_url += "?recursive=1"

            async with await self._http_client() as client:
                resp = await client.get(tree_url, headers=headers)
                resp.raise_for_status()
                data = safe_json_loads(resp.text)

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
                            data = safe_json_loads(resp.text)
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
                            data = safe_json_loads(resp.text)
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
            Search GitHub repos by keyword. Returns names, descriptions, stars, URLs (not code).

            When: Finding repos for a library or topic
            See also: get_repo_tree, get_file_content
            Args: query="web framework", limit=5, language="Python"
            Ex: github_repo_search("requests") → psf/requests
            """
            result = await self._search_repos(query, limit=limit, language=language)
            return serialize_response_with_meta(result)

        async def github_code_search(
            query: str, repo: str | None = None, limit: int = 5
        ) -> CallToolResult:
            """
            Search for code patterns across GitHub. Returns file paths, not content.

            When: Finding code examples or function definitions
            See also: get_file_content (to read found files)
            Note: Rate limited without GITHUB_TOKEN
            Args: query="def parse_args", repo="owner/repo", limit=5
            Ex: github_code_search("async def fetch", repo="psf/requests")
            """
            result = await self._search_code(query, repo=repo, limit=limit)
            return serialize_response_with_meta(result)

        async def list_github_packages(
            owner: str, package_type: str = "container"
        ) -> CallToolResult:
            """
            List GHCR/GitHub packages for a user/org. No global search - owner required.

            When: Finding Docker images or packages on GitHub
            Args: owner="github", package_type="container|npm|maven|rubygems|nuget"
            Ex: list_github_packages("octocat") → container packages list
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
            Get available versions/tags for a GitHub package.

            When: Need version list after finding package via list_github_packages
            Args: owner="github", package_type="container", package_name="rtfd"
            Ex: get_package_versions("octocat", "container", "app") → version list
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
            Fetch README from GitHub repo. Contains project overview and usage.

            When: Need quick project understanding
            See also: get_repo_tree, get_file_content (for deeper exploration)
            Args: repo="owner/repo", max_bytes=20480
            Ex: fetch_github_readme("psf/requests") → README content
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
            return chunk_and_serialize_response(result)

        async def list_repo_contents(repo: str, path: str = "") -> CallToolResult:
            """
            List files/dirs in a GitHub repo directory.

            When: Browsing specific directory contents
            See also: get_repo_tree (full structure), get_file_content (read files)
            Args: repo="owner/repo", path="src/utils"
            Ex: list_repo_contents("psf/requests", "requests") → dir listing
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
            Read file from GitHub repo. UTF-8 only, rejects binary.

            When: Need source code or config file content
            Args: repo="owner/repo", path="src/file.py", max_bytes=102400
            Ex: get_file_content("psf/requests", "requests/api.py") → file content
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
            Get full file tree of a GitHub repo.

            When: Need project structure overview
            See also: get_file_content, list_repo_contents
            Args: repo="owner/repo", recursive=True (for full tree), max_items=1000
            Ex: get_repo_tree("psf/requests", recursive=True) → complete file listing
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
            Get diff between commits/branches/tags in a GitHub repo.

            When: Comparing versions or reviewing changes
            Args: repo="owner/repo", base="main|v1.0.0|sha", head="feature|v1.1.0|sha"
            Ex: get_commit_diff("psf/requests", "v2.28.0", "v2.28.1") → diff output
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
