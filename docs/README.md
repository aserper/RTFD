# Code documentation

This directory describes how the codebase is organized and how the MCP server behaves internally.

## Architecture

- Entry point: `src/RTFD/server.py` contains the main search orchestration tool. Provider-specific tools are in `src/RTFD/providers/`. The console script `rtfd` (declared in `pyproject.toml`) invokes the `run()` function.
- Framework: Uses `mcp.server.fastmcp.FastMCP` to declare tools and run the server over stdio.
- HTTP layer: `httpx.AsyncClient` with a shared `_http_client()` factory that applies timeouts, redirects, and user-agent headers.
- HTML parsing: `BeautifulSoup` for Google result-card scraping.
- Data model: `SearchResult` dataclass for Google hits; other responses are plain dicts for easy serialization over MCP.
- Serialization: Tool responses use `serialize_response_with_meta()` from `utils.py`, which returns `CallToolResult` objects. Format is configurable via `USE_TOON` environment variable (defaults to JSON, optionally TOON for ~30% token reduction).
- Token counting: Optional token statistics in the `meta` field (disabled by default). Enable with `RTFD_TRACK_TOKENS=true` to see JSON vs TOON token counts for comparison.

## Tool behavior

All tools return `CallToolResult` objects containing serialized data (JSON or TOON format based on `USE_TOON` env var) and optional token statistics in the `meta` field:

- `search_library_docs(library, limit=5)` (in `server.py`)
  Orchestrates multiple providers to find documentation. Returns result with `library`, `pypi`, `github_repos`, and `web` keys. Each provider failure is captured as an `*_error` field instead of raising.

- `pypi_metadata(package)` (in `providers/pypi.py`)
  Fetches `https://pypi.org/pypi/{package}/json`. Returns metadata with name, version, summary, home page, docs URL, and project URLs.

- `fetch_pypi_docs(package, max_bytes=20480)` (in `providers/pypi.py`)
  Fetches package README/description from PyPI. Returns content with smart section prioritization and reStructuredText-to-Markdown conversion.

- `npm_metadata(package)` (in `providers/npm.py`)
  Retrieves npm package metadata including documentation URLs when available.

- `fetch_npm_docs(package, max_bytes=20480)` (in `providers/npm.py`)
  Fetches npm package README content with smart section prioritization.

- `github_repo_search(query, limit=5, language="Python")` (in `providers/github.py`)
  Uses GitHub Search API for repos. Adds `language:` qualifier when provided. Reads `GITHUB_TOKEN` for higher rate limits; otherwise relies on anonymous quota. Returns repos with name/description/stars/url/default_branch.

- `github_code_search(query, repo=None, limit=5)` (in `providers/github.py`)
  GitHub code search; if `repo` is given, scopes the query with `repo:owner/name`. Returns code hits with file name, path, repo, and HTML URL.

- `fetch_github_readme(repo, max_bytes=20480)` (in `providers/github.py`)
  Fetches README and documentation from a GitHub repository (format: "owner/repo"). Returns content with metadata.

- `search_crates(query, limit=5)` (in `providers/crates.py`)
  Search for Rust crates on crates.io.

- `crates_metadata(crate)` (in `providers/crates.py`)
  Get detailed metadata for a Rust crate from crates.io.

- `godocs_metadata(package)` (in `providers/godocs.py`)
  Retrieve Go package documentation metadata from godocs.io.

- `zig_docs(query)` (in `providers/zig.py`)
  Search Zig language documentation.

- `search_docker_images(query, limit=5)` (in `providers/dockerhub.py`)
  Search for Docker images on DockerHub. Returns search results with name, description, stars, pull counts, and official image indicators.

- `docker_image_metadata(image)` (in `providers/dockerhub.py`)
  Fetch detailed metadata for a specific Docker image. Supports both official images (e.g., "nginx") and user images (e.g., "user/image"). Returns metadata including stars, pull counts, last update time, description, and repository type.

- `fetch_docker_image_docs(image, max_bytes=20480)` (in `providers/dockerhub.py`)
  Fetch Docker image documentation and description from DockerHub. Combines the description and README content for a Docker image. Returns content with metadata about size and truncation.

## Serialization and Token Counting

Tool responses are handled by `serialize_response_with_meta()` in `utils.py`:

- **Format selection**: Controlled by `USE_TOON` environment variable (defaults to `false` for JSON).
- **TOON format**: When `USE_TOON=true`, uses the `toonify` library to achieve ~30% token reduction compared to JSON, particularly effective for arrays of uniform objects (e.g., search results).
- **Token statistics**: When `RTFD_TRACK_TOKENS=true`, the response includes a `_meta` field with token counts:
  - `tokens_json`: Token count for JSON format
  - `tokens_toon`: Token count for TOON format
  - `tokens_sent`: Actual tokens sent in the response
  - `format`: Active format used ("json" or "toon")
  - `savings_tokens`: Potential token savings (TOON vs JSON)
  - `savings_percent`: Percentage of tokens saved
  - `bytes_json` / `bytes_toon`: Byte sizes for comparison
- **Token counting**: Uses `tiktoken` library with `cl100k_base` encoding (compatible with Claude models).
- **Zero-cost metadata**: Token statistics appear in the `_meta` field of `CallToolResult`, which is visible in Claude Code's special metadata logs but NOT sent to the LLM, costing 0 tokens.
- **Disabled by default**: Token tracking is disabled by default (set `RTFD_TRACK_TOKENS=false` by default). Enable with `RTFD_TRACK_TOKENS=true` to see token statistics.

Example: A result with 2 GitHub repos in TOON vs JSON:
```
# TOON (611 chars)
github_repos[2]{name,stars,url}:
  psf/requests,52000,https://github.com/psf/requests
  requests/toolbelt,8800,https://github.com/requests/toolbelt

# JSON (867 chars)
{"github_repos":[{"name":"psf/requests","stars":52000,"url":"https://github.com/psf/requests"},{"name":"requests/toolbelt","stars":8800,"url":"https://github.com/requests/toolbelt"}]}
```

## Environment Variables

- `USE_TOON` (default: `false`): Set to `true` to enable TOON format serialization for ~30% token reduction.
- `RTFD_TRACK_TOKENS` (default: `false`): Set to `true` to enable token counting with metadata overhead. Token statistics appear in `_meta` field but not in LLM chat.
- `RTFD_FETCH` (default: `true`): Set to `false` to disable documentation content fetching (only metadata will be returned).
- `GITHUB_TOKEN`: Optional GitHub personal access token for higher API rate limits.
- `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`: Optional credentials for Google Custom Search API (used by some tools).

## Error handling

- All external calls use `httpx` with a 15s timeout (`DEFAULT_TIMEOUT`).
- Provider errors (HTTP status, network) are caught and bubbled up as error strings rather than uncaught exceptions, so MCP clients receive structured responses.

## Extensibility points

- Add new providers by creating a new file in `src/RTFD/providers/` with async functions decorated with `@mcp.tool()`.
- All tool functions should:
  1. Import: `from mcp.types import CallToolResult`
  2. Import: `from ..utils import serialize_response_with_meta`
  3. Return: `return serialize_response_with_meta(result_data)`
  4. The return type should be `-> CallToolResult`
- The `serialize_response_with_meta()` function automatically handles:
  - Format selection (JSON vs TOON based on `USE_TOON`)
  - Token counting (if `RTFD_TRACK_TOKENS=true`; disabled by default)
  - Metadata attachment to the response (in `_meta` field, not sent to LLM)
- Adjust headers/timeouts in `_http_client()` to fit hosted environments (proxies, corp networks).
- Modify search heuristics (e.g., language scoping, result limits) in the existing tool functions.

## Development notes

- Dependencies are declared in `pyproject.toml` (Python 3.10+).
  - Core: `mcp`, `httpx`, `beautifulsoup4`, `lxml`
  - Serialization: `toonify` (for TOON format support)
  - Token counting: `tiktoken` (for Claude-compatible token counts)
- The server runs over stdio; no sockets are opened.
- If you change environment-sensitive settings (e.g., `GITHUB_TOKEN`, `USE_TOON`, `RTFD_TRACK_TOKENS`), restart the `rtfd` process to pick them up.
- For testing: Use `pytest` to run the test suite.
