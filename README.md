# ![RTFD Logo](logo.png) RTFD (Read The F*****g Docs) MCP Server

Model Context Protocol (MCP) server that acts as a gateway for coding agents to pull library documentation and related context. It queries PyPI, npm, crates.io, GoDocs, Zig documentation, and GitHub APIs to surface relevant docs in one place.

**Features:**
- **Pluggable Architecture**: Easily add new documentation providers by creating a single provider module
- **Multi-Source Search**: Aggregates results from PyPI, npm, crates.io, GoDocs, Zig docs, GitHub repositories, and GitHub code
- **Token Efficient**: All responses serialized in TOON format (~30% smaller than JSON)
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

## Available Tools

All tool responses are returned in **TOON format** for token efficiency.

**Aggregator:**
- `search_library_docs(library, limit=5)`: Combined lookup across all providers (PyPI, npm, crates.io, GoDocs, Zig, GitHub)

**Individual Providers:**
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

Once configured, Claude Code will have access to all 9 tools and can search library documentation across multiple sources in a single request.

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
        from src.RTFD.utils import to_toon
        result = await self._fetch_from_my_api(query, limit)
        return to_toon(result)

    async def _fetch_from_my_api(self, query: str, limit: int):
        async with await self._http_client_factory() as client:
            # Make HTTP request and parse response
            pass
```

2. **Restart the server** – the new provider is automatically discovered and registered!

3. **No core code changes needed** – your provider is immediately available as a tool.

### Built-in Providers

- **PyPI** (`pypi.py`): Fetches Python package metadata from PyPI
- **npm** (`npm.py`): Fetches JavaScript package metadata from npm registry
- **Crates.io** (`crates.py`): Searches and retrieves Rust crate metadata from crates.io (respects 1 req/sec rate limit)
- **GoDocs** (`godocs.py`): Retrieves Go package documentation from godocs.io
- **Zig** (`zig.py`): Searches Zig programming language documentation
- **GitHub** (`github.py`): Searches GitHub repositories and code

Each provider can be extended or replaced without modifying server.py or other providers.

## Notes

- **TOON format:** All tool responses are serialized to TOON (Token-Oriented Object Notation) format, reducing response size by ~30% compared to JSON. TOON is human-readable and lossless.
- **Rate Limiting:** crates.io provider respects the 1 request/second rate limit enforced by crates.io.
- Network calls fail gracefully with error payloads instead of raising uncaught exceptions.
- Dependencies: `mcp`, `httpx`, `beautifulsoup4`, and `toonify` (for TOON serialization). Adjust `pyproject.toml` if needed.
