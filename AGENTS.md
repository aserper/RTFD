# AGENTS.md

## Setup commands

- Install deps: `uv sync --extra dev`
- Run tests: `uv run pytest`
- Run linting: `uv run ruff check src tests`
- Run formatting: `uv run ruff format src tests`
- Start dev server: `rtfd` (requires uv environment activated or package installed)

## Code style

- Python 3.10+ with type hints
- Use double quotes for strings
- Line length: 100 characters
- Follow Ruff linting rules (E, F, I, N, B, UP, PL, RUF)
- First-party imports: `RTFD` package

## Testing instructions

- Run all tests: `uv run pytest`
- Run without integration tests: `uv run pytest -m "not integration"`
- Run specific test file: `uv run pytest tests/test_server.py`
- Tests use pytest-asyncio for async support
- VCR.py recordings for external API calls (in tests/)

## Project structure

```
src/RTFD/
├── server.py           # Main MCP server and search orchestration
├── providers/          # Provider modules for different sources
│   ├── base.py         # Base provider interface
│   ├── pypi.py         # PyPI (Python packages)
│   ├── npm.py          # npm (JavaScript packages)
│   ├── crates.py       # crates.io (Rust)
│   ├── godocs.py       # Go documentation
│   ├── github.py       # GitHub repos and GHCR
│   ├── dockerhub.py    # Docker images
│   ├── gcp.py          # Google Cloud Platform
│   ├── logscale.py     # LogScale/Humio query language
│   └── zig.py          # Zig documentation
├── cache.py            # Response caching layer
├── chunking.py         # Response chunking for large docs
├── content_utils.py    # Content extraction and conversion
├── token_counter.py    # Token usage tracking
├── utils.py            # Serialization utilities
└── config_generator.py # CLI config generator
```

## Adding a new provider

1. Create new file in `src/RTFD/providers/`
2. Define async functions decorated with `@mcp.tool()`
3. Return `CallToolResult` using `serialize_response_with_meta(result_data)`
4. Import in `server.py` to register tools
5. Add tests in `tests/`

## Tool description format

Follow the token-efficient format (150-250 chars, 3-5 lines):

```python
async def tool_name(param: str) -> CallToolResult:
    """
    One-line summary of what it does.

    When: Brief use case description
    Args: param="example_value"
    Ex: tool_name("arg") → brief result description
    """
```

## Before committing

- Run `uv run ruff check src tests` - fix any lint errors
- Run `uv run pytest` - ensure all tests pass
- Update `CHANGELOG.md` under `[Unreleased]` section
- Do not modify version numbers (automated via semantic-release)

## Commit message format

Use conventional commits style:
- `feat: add new feature`
- `fix: resolve issue with X`
- `docs: update documentation`
- `refactor: simplify logic`
- `test: add new test cases`

## Release process

Automated via GitHub Actions and python-semantic-release:
- Merges to main trigger release workflow
- Version bumps based on commit messages
- CHANGELOG automatically updated
- PyPI package published automatically
