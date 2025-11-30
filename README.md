# ![RTFD Logo](logo.png) RTFD (Read The F*****g Docs) MCP Server

The RTFD (Read The F*****g Docs) MCP Server acts as a bridge between Large Language Models (LLMs) and real-time documentation. It allows coding agents to query package repositories like PyPI, npm, crates.io, GoDocs, DockerHub, and GitHub to retrieve the most up-to-date documentation and context.

This server solves a common problem where LLMs hallucinate APIs or provide outdated code examples because their training data is months or years old. By giving agents access to the actual documentation, RTFD ensures that generated code is accurate and follows current best practices.

## Why use RTFD?

*   **Accuracy:** Agents can access the latest documentation for libraries, ensuring they use the correct version-specific APIs and avoid deprecated methods.
*   **Context Awareness:** Instead of just getting a raw text dump, the server extracts key sections like installation instructions, quickstart guides, and API references, giving the agent exactly what it needs.
*   **Efficiency:** The server supports TOON (Token-Oriented Object Notation) serialization, which can reduce the token cost of documentation responses by approximately 30% compared to standard JSON.
*   **Universality:** It supports multiple ecosystems including Python, JavaScript/TypeScript, Rust, Go, Zig, Docker, and general GitHub repositories, making it a versatile tool for polyglot development.

## Hypothetical Use Cases

Here are a few scenarios where RTFD significantly improves the workflow of an AI coding agent:

### Scenario 1: Updating Legacy Python Code
You task an agent with refactoring a Python script that uses an old version of `pandas`. The agent needs to know if certain functions have been deprecated in the latest release. Using `fetch_pypi_docs`, the agent retrieves the current `pandas` documentation, identifies the deprecated methods, and finds the recommended replacements, ensuring the refactored code is modern and robust.

### Scenario 2: Exploring a New Rust Crate
An agent is assisting with a Rust project and needs to integrate a crate it has not encountered before, such as a specific async runtime or utility library. Instead of guessing the API based on general Rust patterns, the agent uses `crates_metadata` and `search_crates` to verify the crate's existence, version, and feature flags. This prevents compile-time errors and ensures the dependency is correctly defined in `Cargo.toml`.

### Scenario 3: Using Bleeding-Edge Libraries
A developer wants to use a library that was released yesterday and is not yet part of the LLM's training data. Without RTFD, the model would likely hallucinate the library's usage. With RTFD, the agent can use `fetch_github_readme` or `github_code_search` to inspect the repository directly, read the latest README, and understand how to implement the new library correctly.

### Scenario 4: Inspecting Docker Base Images
You are building a containerized application and want to understand how the `python:3.11-slim` image is built to optimize your own Dockerfile. Using `fetch_dockerfile`, the agent retrieves the actual Dockerfile used to build the official image, revealing the underlying Debian version, installed system packages, and environment variables.

## Features

*   **Documentation Content Fetching:** Retrieve actual documentation content (README and key sections) from PyPI, npm, and GitHub rather than just URLs.
*   **Smart Section Extraction:** Automatically prioritizes and extracts relevant sections such as "Installation", "Usage", and "API Reference" to reduce noise.
*   **Format Conversion:** Automatically converts reStructuredText and HTML to Markdown for consistent formatting and easier consumption by LLMs.
*   **Multi-Source Search:** Aggregates results from PyPI, npm, crates.io, GoDocs, Zig docs, DockerHub, and GitHub.
*   **Pluggable Architecture:** Easily add new documentation providers by creating a single provider module.
*   **Token Efficiency:** Optional support for TOON serialization to reduce response size and token usage.
*   **Error Resilience:** Failures in one provider do not crash the server; the system is designed to degrade gracefully.

## Quickstart

1.  Install dependencies (Python 3.10+):
    ```bash
    pip install .
    # or: uv pip install -e .
    ```

2.  Export a GitHub token to avoid strict rate limits (optional but recommended):
    ```bash
    export GITHUB_TOKEN=ghp_your_token_here
    ```

3.  Run the server:
    ```bash
    rtfd
    ```

4.  **Configure Serialization (Optional):**
    By default, the server uses JSON. To use TOON for token efficiency, set `USE_TOON=true`:
    ```bash
    export USE_TOON=true
    rtfd
    ```

5.  **Configure Documentation Fetching (Optional):**
    Content fetching tools are enabled by default. To disable them and only use metadata tools:
    ```bash
    export RTFD_FETCH=false
    rtfd
    ```

6.  **Configure Token Counting (Optional):**
    To enable token counting in response metadata (useful for debugging usage):
    ```bash
    export RTFD_TRACK_TOKENS=true
    rtfd
    ```

## Available Tools

All tool responses are returned in JSON format by default, or TOON if configured.

### Aggregator
*   `search_library_docs(library, limit=5)`: Combined lookup across all providers (PyPI, npm, crates.io, GoDocs, GitHub). Note: Zig and DockerHub are accessed via dedicated tools.

### Documentation Content Fetching
*   `fetch_pypi_docs(package, max_bytes=20480)`: Fetch Python package documentation from PyPI.
*   `fetch_npm_docs(package, max_bytes=20480)`: Fetch npm package documentation.
*   `fetch_github_readme(repo, max_bytes=20480)`: Fetch README from a GitHub repository (format: "owner/repo").
*   `fetch_docker_image_docs(image, max_bytes=20480)`: Fetch Docker image documentation and description from DockerHub (e.g., "nginx", "postgres", "user/image").
*   `fetch_dockerfile(image)`: Fetch the Dockerfile for a Docker image by parsing its description for GitHub links (best-effort).

### Metadata Providers
*   `pypi_metadata(package)`: Fetch Python package metadata.
*   `npm_metadata(package)`: Fetch JavaScript package metadata.
*   `crates_metadata(crate)`: Get Rust crate metadata.
*   `search_crates(query, limit=5)`: Search Rust crates.
*   `godocs_metadata(package)`: Retrieve Go package documentation.
*   `zig_docs(query)`: Search Zig documentation.
*   `docker_image_metadata(image)`: Get DockerHub Docker image metadata (stars, pulls, description, etc.).
*   `search_docker_images(query, limit=5)`: Search for Docker images on DockerHub.
*   `github_repo_search(query, limit=5, language="Python")`: Search GitHub repositories.
*   `github_code_search(query, repo=None, limit=5)`: Search code on GitHub.

## Integration with Claude Code

Add the following to your `~/.claude/settings.json`:

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

Or with environment variables:

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

## Pluggable Architecture

The RTFD server uses a modular architecture. Providers are located in `src/RTFD/providers/` and implement the `BaseProvider` interface. New providers are automatically discovered and registered upon server restart.

To add a custom provider, create a new file in the providers directory inheriting from `BaseProvider`, implement the required methods, and the server will pick it up automatically.

## Notes

*   **Token Counting:** Disabled by default. Set `RTFD_TRACK_TOKENS=true` to see token stats in Claude Code logs.
*   **TOON Format:** Set `USE_TOON=true` to enable.
*   **Rate Limiting:** The crates.io provider respects the 1 request/second limit.
*   **Dependencies:** `mcp`, `httpx`, `beautifulsoup4`, `toonify`, `markdownify`, `docutils`, `tiktoken`.

## Architecture

*   **Entry point:** `src/RTFD/server.py` contains the main search orchestration tool. Provider-specific tools are in `src/RTFD/providers/`.
*   **Framework:** Uses `mcp.server.fastmcp.FastMCP` to declare tools and run the server over stdio.
*   **HTTP layer:** `httpx.AsyncClient` with a shared `_http_client()` factory that applies timeouts, redirects, and user-agent headers.
*   **Data model:** Responses are plain dicts for easy serialization over MCP.
*   **Serialization:** Tool responses use `serialize_response_with_meta()` from `utils.py`. Format is configurable via `USE_TOON` environment variable.
*   **Token counting:** Optional token statistics in the `meta` field (disabled by default). Enable with `RTFD_TRACK_TOKENS=true`.

## Serialization and Token Counting

Tool responses are handled by `serialize_response_with_meta()` in `utils.py`:

*   **Format selection:** Controlled by `USE_TOON` environment variable (defaults to `false` for JSON).
*   **TOON format:** When `USE_TOON=true`, uses the `toonify` library to achieve ~30% token reduction compared to JSON, particularly effective for arrays of uniform objects (e.g., search results).
*   **Token statistics:** When `RTFD_TRACK_TOKENS=true`, the response includes a `_meta` field with token counts (`tokens_json`, `tokens_toon`, `savings_percent`, etc.).
*   **Token counting:** Uses `tiktoken` library with `cl100k_base` encoding (compatible with Claude models).
*   **Zero-cost metadata:** Token statistics appear in the `_meta` field of `CallToolResult`, which is visible in Claude Code's special metadata logs but NOT sent to the LLM, costing 0 tokens.

Example: A result with 2 GitHub repos in TOON vs JSON:

```
# TOON (611 chars)
github_repos[2]{name,stars,url}:
  psf/requests,52000,https://github.com/psf/requests
  requests/toolbelt,8800,https://github.com/requests/toolbelt

# JSON (867 chars)
{"github_repos":[{"name":"psf/requests","stars":52000,"url":"https://github.com/psf/requests"},{"name":"requests/toolbelt","stars":8800,"url":"https://github.com/requests/toolbelt"}]}
```

## Extensibility & Development

### Adding Providers
The RTFD server uses a modular architecture. Providers are located in `src/RTFD/providers/` and implement the `BaseProvider` interface. New providers are automatically discovered and registered upon server restart.

To add a custom provider:
1.  Create a new file in `src/RTFD/providers/`.
2.  Define async functions decorated with `@mcp.tool()`.
3.  Ensure tools return `CallToolResult` using `serialize_response_with_meta(result_data)`.

### Development Notes
*   **Dependencies:** Declared in `pyproject.toml` (Python 3.10+).
*   **Testing:** Use `pytest` to run the test suite.
*   **Environment:** If you change environment-sensitive settings (e.g., `GITHUB_TOKEN`, `USE_TOON`), restart the `rtfd` process.

