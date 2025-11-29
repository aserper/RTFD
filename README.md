# ![RTFD Logo](logo.png) RTFD (Read The F*****g Docs) MCP Server

Model Context Protocol (MCP) server that acts as a gateway for coding agents to pull library documentation and related context. It queries PyPI, npm, crates.io, GoDocs, Zig documentation, and GitHub APIs to surface relevant docs in one place.

**Features:**
- **Documentation Content Fetching**: Retrieve actual documentation content (README + key sections) instead of just URLs from PyPI, npm, and GitHub
- **Smart Section Extraction**: Automatically prioritizes and extracts relevant documentation sections (installation, quickstart, API reference, etc.)
- **Format Conversion**: Automatically converts reStructuredText and HTML to Markdown for consistent formatting
- **Pluggable Architecture**: Easily add new documentation providers by creating a single provider module
- **Multi-Source Search**: Aggregates results from PyPI, npm, crates.io, GoDocs, Zig docs, GitHub repositories, and GitHub code
- **Token Counting**: Every response includes token statistics showing JSON vs TOON token usage and potential savings (visible in Claude Code UI, costs 0 tokens)
- **Token Efficient**: Responses can be serialized in TOON format (~30% smaller than JSON) by setting `USE_TOON=true`
- **Error Resilient**: Provider failures are isolated; one API failure doesn't crash the server
- **Auto-Discovery**: New providers are automatically discovered and registered

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
   rtfd
   ```

4. Configure serialization (optional):
   By default, the server uses JSON serialization. To use TOON for token efficiency, set `USE_TOON=true`:
   ```bash
   export USE_TOON=true
   rtfd
   ```

5. Configure documentation fetching (optional):
   By default, documentation content fetching tools are enabled (`fetch_pypi_docs`, `fetch_npm_docs`, `fetch_github_readme`).
   To disable them and only use metadata tools, set `RTFD_FETCH=false`:
   ```bash
   export RTFD_FETCH=false
   rtfd
   ```
   Accepted values for disabling: `false`, `0`, `no` (case-insensitive)

6. Configure token counting (optional):
   By default, token counting is enabled and all tool responses include token statistics in the response metadata (visible in Claude Code UI, costs 0 tokens).
   To disable token counting for better performance, set `RTFD_TRACK_TOKENS=false`:
   ```bash
   export RTFD_TRACK_TOKENS=false
   rtfd
   ```

## Available Tools

All tool responses are returned in **JSON format** by default. This can be changed to TOON by setting `USE_TOON=true`.

**Aggregator:**
- `search_library_docs(library, limit=5)`: Combined lookup across all providers (PyPI, npm, crates.io, GoDocs, Zig, GitHub)

**Documentation Content Fetching:**
- `fetch_pypi_docs(package, max_bytes=20480)`: Fetch Python package documentation from PyPI (includes README/description with smart section prioritization)
- `fetch_npm_docs(package, max_bytes=20480)`: Fetch npm package documentation (README with section prioritization)
- `fetch_github_readme(repo, max_bytes=20480)`: Fetch README from GitHub repository (format: "owner/repo")

**Metadata Providers:**
- `pypi_metadata(package)`: Fetch Python package metadata from PyPI
- `npm_metadata(package)`: Fetch JavaScript package metadata from npm
- `crates_metadata(crate)`: Get Rust crate metadata from crates.io
- `search_crates(query, limit=5)`: Search Rust crates on crates.io
- `godocs_metadata(package)`: Retrieve Go package documentation from godocs.io
- `zig_docs(query)`: Search Zig programming language documentation
- `github_repo_search(query, limit=5, language="Python")`: Search GitHub repositories
- `github_code_search(query, repo=None, limit=5)`: Search code on GitHub

## Integration with Claude Code

Once the server is running, you can connect it to [Claude Code](https://claude.com/claude-code) (or any other MCP client).

### Claude Code Configuration

Add the following to your `~/.claude/settings.json` (or create it if it doesn't exist):

```json
{
  "mcpServers": {
    "rtfd": {
      "command": "rtfd",
      "type": "stdio"
    }
  }
}
```

Or, if you want to run it with a specific environment (e.g., with a GitHub token):

```json
{
  "mcpServers": {
    "rtfd": {
      "command": "bash",
      "args": ["-c", "export GITHUB_TOKEN=your_token_here && rtfd"],
      "type": "stdio"
    }
  }
}
```

Once configured, Claude Code will have access to all 13 tools and can search library documentation across multiple sources in a single request. Each tool response includes token statistics in the metadata showing current usage and potential TOON savings.

## Integration with Other MCP Clients

This MCP server works with any MCP-compatible client, including:
- **Cursor**: Add to your `.cursor/settings.json` with similar configuration
- **Cline**: Configure via environment or MCP server settings
- **Custom Agents**: Any application using the [MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

The server communicates over **stdio** (standard input/output), making it compatible with any client that supports the MCP protocol.

## Pluggable Architecture

The RTFD server uses a pluggable provider architecture, making it easy to add new documentation sources without modifying the core server code.

### How It Works

- **Providers** are modular plugins in `src/RTFD/providers/`
- Each provider implements the `BaseProvider` interface
- New providers are **automatically discovered** and registered
- Providers can expose **multiple tools** (e.g., GitHub has both repo and code search)
- Each provider has **isolated error handling** (one failure doesn't crash others)

### Adding a Custom Provider

To add a new documentation provider:

1. **Create a provider file** in `src/RTFD/providers/my_provider.py`:

```python
from src.RTFD.providers.base import BaseProvider, ProviderMetadata, ProviderResult

class MyProvider(BaseProvider):
    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="my_provider",
            description="Search documentation from my custom source",
            expose_as_tool=True,
            tool_names=["my_search"],
            supports_library_search=True
        )

    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        # Your implementation here
        data = await self._fetch_from_my_api(library, limit)
        return ProviderResult(success=True, data=data, provider_name="my_provider")

    def get_tools(self):
        return {
            "my_search": self._my_search
        }

    async def _my_search(self, query: str, limit: int = 5) -> str:
        from src.RTFD.utils import serialize_response
        result = await self._fetch_from_my_api(query, limit)
        return serialize_response(result)

    async def _fetch_from_my_api(self, query: str, limit: int):
        async with await self._http_client_factory() as client:
            # Make HTTP request and parse response
            pass
```

2. **Restart the server** – the new provider is automatically discovered and registered!

3. **No core code changes needed** – your provider is immediately available as a tool.

### Built-in Providers

- **PyPI** (`pypi.py`): Fetches Python package metadata and documentation content from PyPI (auto-converts reStructuredText to Markdown)
- **npm** (`npm.py`): Fetches JavaScript package metadata and documentation content from npm registry
- **GitHub** (`github.py`): Searches repositories and code; fetches README content from repositories
- **Crates.io** (`crates.py`): Searches and retrieves Rust crate metadata from crates.io (respects 1 req/sec rate limit)
- **GoDocs** (`godocs.py`): Retrieves Go package documentation from godocs.io
- **Zig** (`zig.py`): Searches Zig programming language documentation

Each provider can be extended or replaced without modifying server.py or other providers.

## Token Counting

RTFD automatically tracks token consumption for every API call and displays statistics in the response metadata. This feature is designed to help you understand token usage without adding any cost to your LLM.

### How It Works

- **Token Statistics in Metadata**: Every tool response includes a `meta` field with token statistics
- **Zero LLM Cost**: Token counts appear in Claude Code's UI but are NOT sent to the LLM (costs 0 tokens)
- **JSON vs TOON Comparison**: Shows token count for both formats + potential savings percentage
- **Always Calculated**: By default, token stats are included on every response

### What You'll See

When calling any rtfd tool in Claude Code, the response metadata will include:

```json
{
  "token_stats": {
    "tokens_json": 1247,      // tokens if using JSON
    "tokens_toon": 823,       // tokens if using TOON
    "tokens_sent": 1247,      // actual tokens in this response
    "format": "json",         // which format is active
    "savings_tokens": 424,    // how many tokens TOON would save
    "savings_percent": 34.0,  // percentage savings
    "bytes_json": 5234,       // size in bytes (JSON)
    "bytes_toon": 3456        // size in bytes (TOON)
  }
}
```

This allows you to see at a glance whether using `USE_TOON=true` would provide meaningful token savings for your workload.

### Controlling Token Counting

- **Enable (default)**: `RTFD_TRACK_TOKENS=true` - Calculate tokens for both formats on every response
- **Disable**: `RTFD_TRACK_TOKENS=false` - Only serialize to active format, skip token counting (faster)

Disable token counting if you experience performance issues or don't need the statistics:
```bash
export RTFD_TRACK_TOKENS=false
rtfd
```

## Notes

- **Token Counting:** By default, RTFD calculates token statistics comparing JSON and TOON formats for every response. Statistics appear in response metadata (visible in Claude Code UI but cost 0 tokens to the LLM). Disable with `RTFD_TRACK_TOKENS=false` if you prefer better performance over token stats.
- **TOON format:** Tool responses can be serialized to TOON (Token-Oriented Object Notation) format, reducing response size by ~30% compared to JSON. TOON is human-readable and lossless. Set `USE_TOON=true` to enable TOON serialization.
- **Documentation Fetching:** Content fetching tools (`fetch_pypi_docs`, `fetch_npm_docs`, `fetch_github_readme`) are enabled by default. Set `RTFD_FETCH=false` to disable and only use metadata tools.
- **Rate Limiting:** crates.io provider respects the 1 request/second rate limit enforced by crates.io.
- Network calls fail gracefully with error payloads instead of raising uncaught exceptions.
- Dependencies: `mcp`, `httpx`, `beautifulsoup4`, `toonify` (for TOON serialization), `markdownify`, `docutils` (for content fetching), and `tiktoken` (for token counting). Adjust `pyproject.toml` if needed.
