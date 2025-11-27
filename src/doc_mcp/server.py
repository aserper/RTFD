"""
MCP gateway server that surfaces library documentation by querying Google, GitHub, and PyPI.

The server exposes tools meant for coding agents to quickly pull reference material without
having to juggle multiple sources. Network-heavy calls are written defensively so the agent
gets a useful error payload instead of a crash when a provider is unavailable.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

USER_AGENT = (
    "doc-mcp/0.1 (+https://github.com/) "
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 15.0

mcp = FastMCP("doc-mcp-gateway")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def as_dict(self) -> Dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


async def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )


async def search_google(query: str, limit: int = 5) -> List[SearchResult]:
    """Scrape Google search result cards. Lightweight and dependency-free."""
    async with await _http_client() as client:
        resp = await client.get("https://www.google.com/search", params={"q": query})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

    results: List[SearchResult] = []
    for block in soup.select("div.g"):
        anchor = block.find("a")
        if not anchor or not anchor.get("href"):
            continue
        title = anchor.get_text(" ", strip=True)
        snippet = block.get_text(" ", strip=True)
        results.append(SearchResult(title=title, url=anchor["href"], snippet=snippet))
        if len(results) >= limit:
            break

    return results


async def search_github_repos(
    query: str, limit: int = 5, language: Optional[str] = "Python"
) -> List[Dict[str, Any]]:
    """Query GitHub's repository search API."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    params = {"q": query, "per_page": str(limit)}
    if language:
        params["q"] = f"{query} language:{language}"

    async with await _http_client() as client:
        resp = await client.get("https://api.github.com/search/repositories", params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    repos: List[Dict[str, Any]] = []
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


async def search_github_code(query: str, repo: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Search code on GitHub; optionally scoping to a repository."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    search_query = query
    if repo:
        search_query = f"{query} repo:{repo}"

    params = {"q": search_query, "per_page": str(limit)}
    async with await _http_client() as client:
        resp = await client.get("https://api.github.com/search/code", params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    code_hits: List[Dict[str, Any]] = []
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


async def fetch_pypi_metadata(package: str) -> Dict[str, Any]:
    """Pull package metadata from the PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    async with await _http_client() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        payload = resp.json()

    info = payload.get("info", {})
    return {
        "name": info.get("name"),
        "summary": info.get("summary") or "",
        "version": info.get("version"),
        "home_page": info.get("home_page"),
        "docs_url": info.get("project_urls", {}).get("Documentation")
        if isinstance(info.get("project_urls"), dict)
        else None,
        "project_urls": info.get("project_urls") or {},
    }


async def locate_library_docs(library: str, limit: int = 5) -> Dict[str, Any]:
    """
    Try to find documentation links for a given library using PyPI first,
    then GitHub repo search, and finally Google.
    """
    result: Dict[str, Any] = {"library": library}

    try:
        result["pypi"] = await fetch_pypi_metadata(library)
    except httpx.HTTPStatusError as exc:
        result["pypi_error"] = f"PyPI returned {exc.response.status_code}"
    except httpx.HTTPError as exc:
        result["pypi_error"] = f"PyPI request failed: {exc}"

    try:
        result["github_repos"] = await search_github_repos(f"{library} python", limit=limit)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response is not None else ""
        result["github_error"] = f"GitHub returned {exc.response.status_code} {detail}"
    except httpx.HTTPError as exc:
        result["github_error"] = f"GitHub request failed: {exc}"

    try:
        result["web"] = [hit.as_dict() for hit in await search_google(f"{library} python documentation", limit=limit)]
    except httpx.HTTPStatusError as exc:
        result["google_error"] = f"Google returned {exc.response.status_code}"
    except httpx.HTTPError as exc:
        result["google_error"] = f"Google request failed: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        result["google_error"] = f"Google parsing failed: {exc}"

    return result


@mcp.tool(
    description="Find docs for a library using PyPI metadata, GitHub repos, and Google search combined."
)
async def search_library_docs(library: str, limit: int = 5) -> Dict[str, Any]:
    return await locate_library_docs(library, limit=limit)


@mcp.tool(
    description="Run a general Google search and return result cards (scraped HTML, no API key required)."
)
async def google_search(query: str, limit: int = 5) -> List[Dict[str, str]]:
    hits = await search_google(query, limit=limit)
    return [hit.as_dict() for hit in hits]


@mcp.tool(description="Search GitHub repositories relevant to a library or topic.")
async def github_repo_search(query: str, limit: int = 5, language: Optional[str] = "Python") -> List[Dict[str, Any]]:
    return await search_github_repos(query, limit=limit, language=language)


@mcp.tool(description="Search GitHub code (optionally scoped to a repository).")
async def github_code_search(query: str, repo: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    return await search_github_code(query, repo=repo, limit=limit)


@mcp.tool(description="Retrieve PyPI package metadata including documentation URLs when available.")
async def pypi_metadata(package: str) -> Dict[str, Any]:
    return await fetch_pypi_metadata(package)


def run() -> None:
    """Entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    run()
