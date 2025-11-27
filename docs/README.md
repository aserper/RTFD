# Code documentation

This directory describes how the codebase is organized and how the MCP server behaves internally.

## Architecture

- Entry point: `src/doc_mcp/server.py` contains all tool implementations and the console entry `run()`. The console script `doc-mcp-server` (declared in `pyproject.toml`) invokes this.
- Framework: Uses `mcp.server.fastmcp.FastMCP` to declare tools and run the server over stdio.
- HTTP layer: `httpx.AsyncClient` with a shared `_http_client()` factory that applies timeouts, redirects, and user-agent headers.
- HTML parsing: `BeautifulSoup` for Google result-card scraping.
- Data model: `SearchResult` dataclass for Google hits; other responses are plain dicts for easy serialization over MCP.

## Tool behavior

- `search_library_docs(library, limit=5)`  
  Calls, in order: `fetch_pypi_metadata`, `search_github_repos`, and `search_google`. Each provider failure is captured as an `*_error` field instead of raising.

- `google_search(query, limit=5)`  
  Scrapes `https://www.google.com/search` result blocks (`div.g`). Returns `[{title, url, snippet}]`. Best effort; may yield fewer results if Google throttles.

- `github_repo_search(query, limit=5, language="Python")`  
  Uses GitHub Search API for repos. Adds `language:` qualifier when provided. Reads `GITHUB_TOKEN` for higher rate limits; otherwise relies on anonymous quota. Returns name/description/stars/url/default_branch.

- `github_code_search(query, repo=None, limit=5)`  
  GitHub code search; if `repo` is given, scopes the query with `repo:owner/name`. Returns file name, path, repo, and HTML URL.

- `pypi_metadata(package)`  
  Fetches `https://pypi.org/pypi/{package}/json` and returns core metadata plus `project_urls` and any docs URL if present.

## Error handling

- All external calls use `httpx` with a 15s timeout (`DEFAULT_TIMEOUT`).
- Provider errors (HTTP status, network) are caught and bubbled up as error strings rather than uncaught exceptions, so MCP clients receive structured responses.

## Extensibility points

- Add new providers by creating async functions and decorating with `@mcp.tool`.
- Adjust headers/timeouts in `_http_client()` to fit hosted environments (proxies, corp networks).
- Modify search heuristics (e.g., language scoping, result limits) in the existing tool functions.

## Development notes

- Dependencies are declared in `pyproject.toml` (Python 3.10+).
- The server runs over stdio; no sockets are opened.
- If you change environment-sensitive settings (e.g., `GITHUB_TOKEN`), restart the `doc-mcp-server` process to pick them up.
