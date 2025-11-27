# Code documentation

This directory describes how the codebase is organized and how the MCP server behaves internally.

## Architecture

- Entry point: `src/doc_mcp/server.py` contains all tool implementations and the console entry `run()`. The console script `doc-mcp-server` (declared in `pyproject.toml`) invokes this.
- Framework: Uses `mcp.server.fastmcp.FastMCP` to declare tools and run the server over stdio.
- HTTP layer: `httpx.AsyncClient` with a shared `_http_client()` factory that applies timeouts, redirects, and user-agent headers.
- HTML parsing: `BeautifulSoup` for Google result-card scraping.
- Data model: `SearchResult` dataclass for Google hits; other responses are plain dicts for easy serialization over MCP.
- Serialization: All tool responses are serialized to TOON format (Token-Oriented Object Notation) using the `toonify` library for token efficiency (~30% reduction vs JSON).

## Tool behavior

All tools return TOON-formatted strings for token efficiency:

- `search_library_docs(library, limit=5)`
  Calls, in order: `fetch_pypi_metadata`, `search_github_repos`, and `search_google`. Returns TOON-serialized result with `library`, `pypi`, `github_repos`, and `web` keys. Each provider failure is captured as an `*_error` field instead of raising.

- `google_search(query, limit=5, use_api=False)`
  If `use_api=True` and `GOOGLE_API_KEY` + `GOOGLE_CSE_ID` are set, uses Google Custom Search JSON API; otherwise scrapes `https://www.google.com/search` result blocks (`div.g`). Returns TOON-serialized array with `[{title, url, snippet}]` structure. Best effort; may yield fewer results if throttled.

- `github_repo_search(query, limit=5, language="Python")`
  Uses GitHub Search API for repos. Adds `language:` qualifier when provided. Reads `GITHUB_TOKEN` for higher rate limits; otherwise relies on anonymous quota. Returns TOON-serialized repos with name/description/stars/url/default_branch.

- `github_code_search(query, repo=None, limit=5)`
  GitHub code search; if `repo` is given, scopes the query with `repo:owner/name`. Returns TOON-serialized code hits with file name, path, repo, and HTML URL.

- `pypi_metadata(package)`
  Fetches `https://pypi.org/pypi/{package}/json`. Returns TOON-serialized metadata with name, version, summary, home page, docs URL, and project URLs.

## TOON Serialization

All tool responses are converted to TOON format using the `toonify` library:

- The `_to_toon(data)` helper function converts Python dicts/lists to TOON strings.
- Each `@mcp.tool` decorated function calls `_to_toon()` before returning.
- TOON format achieves ~30% size reduction compared to JSON, particularly effective for arrays of uniform objects (e.g., search results).
- The format is lossless: responses can be decoded back to the original Python data structures if needed.
- Benefits: reduced token usage for LLM context, improved efficiency for bandwidth-constrained environments, human-readable tabular format.

Example: A result with 2 GitHub repos in TOON vs JSON:
```
# TOON (611 chars)
github_repos[2]{name,stars,url}:
  psf/requests,52000,https://github.com/psf/requests
  requests/toolbelt,8800,https://github.com/requests/toolbelt

# JSON (867 chars)
{"github_repos":[{"name":"psf/requests","stars":52000,"url":"https://github.com/psf/requests"},{"name":"requests/toolbelt","stars":8800,"url":"https://github.com/requests/toolbelt"}]}
```

## Error handling

- All external calls use `httpx` with a 15s timeout (`DEFAULT_TIMEOUT`).
- Provider errors (HTTP status, network) are caught and bubbled up as error strings rather than uncaught exceptions, so MCP clients receive structured responses.

## Extensibility points

- Add new providers by creating async functions and decorating with `@mcp.tool(description="... Returns data in TOON format.")`.
- Remember to call `_to_toon(result)` before returning from tool functions to serialize to TOON format.
- Adjust headers/timeouts in `_http_client()` to fit hosted environments (proxies, corp networks).
- Modify search heuristics (e.g., language scoping, result limits) in the existing tool functions.

## Development notes

- Dependencies are declared in `pyproject.toml` (Python 3.10+).
- The server runs over stdio; no sockets are opened.
- If you change environment-sensitive settings (e.g., `GITHUB_TOKEN`), restart the `doc-mcp-server` process to pick them up.
