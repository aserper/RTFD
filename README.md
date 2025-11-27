# doc-mcp

Model Context Protocol server that acts as a gateway for coding agents to pull library documentation and related context. It queries Google (HTML scrape), GitHub search APIs, and PyPI metadata to surface relevant docs in one place.

## Quickstart

1. Install dependencies (Python 3.10+):
   ```bash
   pip install .
   # or: uv pip install -e .
   ```
2. Export a GitHub token to avoid strict rate limits (optional but recommended):
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   ```
3. Run the server:
   ```bash
   doc-mcp-server
   ```

The server exposes MCP tools:
- `search_library_docs(library, limit=5)`: Combined lookup using PyPI, GitHub, and Google.
- `google_search(query, limit=5)`: General Google card scrape (no API key).
- `github_repo_search(query, limit=5, language="Python")`
- `github_code_search(query, repo=None, limit=5)`
- `pypi_metadata(package)`

## Notes

- Google scraping is best-effort and may return fewer results if Google throttles anonymous traffic; add a proxy or API if needed.
- Network calls fail gracefully with error payloads instead of raising uncaught exceptions.
- This project only depends on standard Python plus `mcp`, `httpx`, and `beautifulsoup4`; adjust `pyproject.toml` if you need an alternative HTTP client.
