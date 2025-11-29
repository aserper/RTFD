# ![RTFD Logo](logo.png) RTFD (Read The F*****g Docs) MCP Server

The RTFD (Read The F*****g Docs) MCP Server acts as a bridge between Large Language Models (LLMs) and real-time documentation. It allows coding agents to query package repositories like PyPI, npm, crates.io, GoDocs, and GitHub to retrieve the most up-to-date documentation and context.

This server solves a common problem where LLMs hallucinate APIs or provide outdated code examples because their training data is months or years old. By giving agents access to the actual documentation, RTFD ensures that generated code is accurate and follows current best practices.

## Why use RTFD?

*   **Accuracy:** Agents can access the latest documentation for libraries, ensuring they use the correct version-specific APIs and avoid deprecated methods.
*   **Context Awareness:** Instead of just getting a raw text dump, the server extracts key sections like installation instructions, quickstart guides, and API references, giving the agent exactly what it needs.
*   **Efficiency:** The server supports TOON (Token-Oriented Object Notation) serialization, which can reduce the token cost of documentation responses by approximately 30% compared to standard JSON.
*   **Universality:** It supports multiple ecosystems including Python, JavaScript/TypeScript, Rust, Go, Zig, and general GitHub repositories, making it a versatile tool for polyglot development.

## Hypothetical Use Cases

Here are a few scenarios where RTFD significantly improves the workflow of an AI coding agent:

### Scenario 1: Updating Legacy Python Code
You task an agent with refactoring a Python script that uses an old version of `pandas`. The agent needs to know if certain functions have been deprecated in the latest release. Using `fetch_pypi_docs`, the agent retrieves the current `pandas` documentation, identifies the deprecated methods, and finds the recommended replacements, ensuring the refactored code is modern and robust.

### Scenario 2: Exploring a New Rust Crate
An agent is assisting with a Rust project and needs to integrate a crate it has not encountered before, such as a specific async runtime or utility library. Instead of guessing the API based on general Rust patterns, the agent uses `crates_metadata` and `search_crates` to verify the crate's existence, version, and feature flags. This prevents compile-time errors and ensures the dependency is correctly defined in `Cargo.toml`.

### Scenario 3: Using Bleeding-Edge Libraries
A developer wants to use a library that was released yesterday and is not yet part of the LLM's training data. Without RTFD, the model would likely hallucinate the library's usage. With RTFD, the agent can use `fetch_github_readme` or `github_code_search` to inspect the repository directly, read the latest README, and understand how to implement the new library correctly.

## Features

*   **Documentation Content Fetching:** Retrieve actual documentation content (README and key sections) from PyPI, npm, and GitHub rather than just URLs.
*   **Smart Section Extraction:** Automatically prioritizes and extracts relevant sections such as "Installation", "Usage", and "API Reference" to reduce noise.
*   **Format Conversion:** Automatically converts reStructuredText and HTML to Markdown for consistent formatting and easier consumption by LLMs.
*   **Multi-Source Search:** Aggregates results from PyPI, npm, crates.io, GoDocs, Zig docs, and GitHub.
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
*   `search_library_docs(library, limit=5)`: Combined lookup across all providers (PyPI, npm, crates.io, GoDocs, Zig, GitHub).

### Documentation Content Fetching
*   `fetch_pypi_docs(package, max_bytes=20480)`: Fetch Python package documentation from PyPI.
*   `fetch_npm_docs(package, max_bytes=20480)`: Fetch npm package documentation.
*   `fetch_github_readme(repo, max_bytes=20480)`: Fetch README from a GitHub repository (format: "owner/repo").

### Metadata Providers
*   `pypi_metadata(package)`: Fetch Python package metadata.
*   `npm_metadata(package)`: Fetch JavaScript package metadata.
*   `crates_metadata(crate)`: Get Rust crate metadata.
*   `search_crates(query, limit=5)`: Search Rust crates.
*   `godocs_metadata(package)`: Retrieve Go package documentation.
*   `zig_docs(query)`: Search Zig documentation.
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
