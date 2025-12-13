# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Container Registry (GHCR) support tools:
  - `list_github_packages`: List packages for a user or organization
  - `get_package_versions`: Get versions for a specific package

### Changed

### Fixed

## [0.5.0] - 2025-12-13

### Added
- **Docker Support**: Official Docker container available on GHCR (`ghcr.io/aserper/rtfd`)
  - Runs independently with all dependencies pre-installed
  - Supports all environment variables for configuration
  - Optimized image size using `uv` and multi-stage builds

### Changed

### Fixed

## [0.4.1] - 2025-12-07

### Added

### Changed

### Fixed
- Fixed `ruff` configuration in `pyproject.toml` to use valid `target-version` (fixes CI failure)

## [0.4.0] - 2025-12-07

### Added
- Configurable GitHub authentication via `GITHUB_AUTH` environment variable
  - Supports `token` (default), `cli`, `auto`, or `disabled` modes
  - Allows authentication via GitHub CLI (`gh auth token`) without manual token management

### Changed
- Updated documentation examples to include `GITHUB_AUTH` configuration for all supported clients (Cursor, Windsurf, Gemini, Codex)

### Fixed

## [0.3.1] - 2025-12-04

### Fixed
- Provider tools are now properly registered with MCP, fixing the issue where tools like `get_commit_diff`, `list_repo_contents`, `get_file_content`, and `get_repo_tree` were not appearing in the tools list

## [0.3.0] - 2025-12-03

### Added
- New `get_commit_diff` tool in GitHub provider to compare commits, branches, or tags.

### Changed

### Fixed

## [0.2.6] - 2025-12-03

### Added

### Changed

### Fixed
- Fixed "Invalid control character" error by redirecting all internal logging/prints to stderr to prevent MCP protocol corruption.

## [0.2.5] - 2025-12-03

### Added
- Enhanced all tool descriptions with detailed usage guidance across all providers
  - Added "USE THIS WHEN" sections to help LLMs choose the right tool
  - Added "BEST FOR" sections highlighting key strengths
  - Added workflow guidance showing which tools to use together
  - Added concrete examples for each tool
  - Improves tool selection by providing clear distinctions between metadata vs. content tools
- File browsing and content fetching capabilities to GitHub provider
  - `list_repo_contents()` - Browse directory structure in repositories
  - `get_file_content()` - Read actual source code files (UTF-8 text only)
  - `get_repo_tree()` - Get complete file tree with recursive option
  - Supports Base64 decoding, binary file detection, and safe UTF-8 truncation
- Renamed MCP server to "RTFD!" for friendlier tool names
  - Tools now appear as `mcp__RTFD!__<tool_name>` instead of `mcp__rtfd-gateway__<tool_name>`
- Automated changelog management in release workflow
  - `scripts/update_changelog.py` handles versioning, validation, and release notes extraction
  - Release workflow now automatically updates CHANGELOG.md, bumps version, and creates release notes

### Changed
- GitHub provider now offers comprehensive code exploration beyond just README fetching
- Release process is now fully automated including changelog updates
  - Contributors only need to add changes to `[Unreleased]`
  - Version headers and date stamping are handled automatically by the workflow

## [0.2.4] - 2025-01-02

### Fixed
- Prioritize local service mapping over cloud.google.com search in GCP provider
  - Fixes issue where generic blog posts were returned instead of actual services
  - Queries like "big" now correctly return BigQuery/Bigtable instead of blog content
- Update GCP partial match test to mock cloud.google.com search

## [0.2.3] - 2025-01-02

### Fixed
- Prioritize specific GCP search results over generic local matches
  - Improved search relevance for partial matches
  - Prepend cloud.google.com results when they are more specific than local mapping

### Changed
- Updated GCP search tool description to mention cloud.google.com search capability
- Updated GCP provider documentation to explain hybrid search approach

## [0.2.2] - 2024-12-31

### Added
- PyPI package verification check using `VERIFIED_BY_PYPI` environment variable
  - Optional security feature to only allow PyPI-verified packages
  - Can be bypassed with `ignore_verification` parameter if needed
- Enhanced GCP service search with cloud.google.com integration
  - Now searches Google Cloud's website in addition to local service mapping
  - Better coverage for services not in the local mapping

### Fixed
- `fetch_gcp_service_docs` now searches for services when direct match fails
  - Automatically finds correct service URL even with partial/fuzzy names
  - Handles multi-word service names correctly

## [0.2.1] - 2024-12-30

### Fixed
- Improved GCP provider search to handle multi-word queries
  - Queries like "gke audit policy configuration" now work correctly
  - Extracts service name from multi-word queries intelligently

### Changed
- Clarified privacy statement in README
- Removed deprecated release and publish workflows

### Fixed
- Resolved workflow trigger issue with combined release and publish workflow

## [0.2.0] - 2024-12-29

### Added
- **GCP (Google Cloud Platform) documentation provider**
  - Search for GCP services by name or keyword
  - Fetch documentation from cloud.google.com
  - Hybrid approach using local service mapping and GitHub API fallback
  - Supports 60+ GCP services including Cloud Storage, Compute Engine, BigQuery, etc.
  - Converts HTML documentation to clean Markdown format
  - Smart section prioritization (Overview, Quickstart, API Reference)
  - `search_gcp_services()` tool for finding GCP services
  - `fetch_gcp_service_docs()` tool for retrieving service documentation

## [0.1.2] - 2024-12-28

### Added
- Integration tests with VCR cassettes for all API providers
  - PyPI, npm, crates.io, GoDocs, GCP, and GitHub integration tests
  - Recorded HTTP interactions for fast, deterministic testing
  - Tests verify actual API response structures

### Fixed
- Replace deprecated `writer_name` with `writer` argument in docutils
  - Fixes compatibility with newer docutils versions
  - Resolves deprecation warnings in reStructuredText conversion

### Changed
- Removed release process from contributing guide (maintainers only)
- Clarified that release process is for maintainers only

## [0.1.1] - 2024-12-27

### Changed
- Initial public release
- MCP server providing documentation access across multiple ecosystems

### Features
- **Multi-source documentation support:**
  - PyPI (Python packages)
  - npm (JavaScript/TypeScript packages)
  - crates.io (Rust crates)
  - GoDocs (Go packages)
  - Zig language documentation
  - DockerHub (Docker images)
  - GitHub repositories

- **Core capabilities:**
  - Metadata retrieval for packages/images
  - README/documentation content fetching
  - Smart section extraction and prioritization
  - Format conversion (reStructuredText/HTML to Markdown)
  - Aggregated library search across all providers

- **Tools provided:**
  - `search_library_docs` - Search across all providers
  - `pypi_metadata` & `fetch_pypi_docs` - Python packages
  - `npm_metadata` & `fetch_npm_docs` - JavaScript packages
  - `crates_metadata` & `search_crates` - Rust crates
  - `godocs_metadata` & `fetch_godocs_docs` - Go packages
  - `zig_docs` - Zig language documentation
  - `search_docker_images`, `docker_image_metadata`, `fetch_docker_image_docs`, `fetch_dockerfile` - Docker images
  - `github_repo_search`, `github_code_search`, `fetch_github_readme` - GitHub repositories

- **Architecture:**
  - Pluggable provider system with auto-discovery
  - FastMCP-based server implementation
  - Error-resilient design (one provider failure doesn't crash server)
  - Privacy-focused (runs entirely locally, no data collection)

[Unreleased]: https://github.com/aserper/rtfd/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/aserper/rtfd/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/aserper/rtfd/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/aserper/rtfd/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/aserper/rtfd/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/aserper/rtfd/compare/v0.2.6...v0.3.0
[0.2.6]: https://github.com/aserper/rtfd/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/aserper/rtfd/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/aserper/rtfd/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/aserper/rtfd/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/aserper/rtfd/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/aserper/rtfd/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/aserper/rtfd/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/aserper/rtfd/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/aserper/rtfd/releases/tag/v0.1.1
