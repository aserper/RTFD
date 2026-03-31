---
name: using-rtfd
description: Use when needing to look up library documentation, package metadata, Docker images, GitHub repos, GCP services, LogScale query syntax, or Zig docs. Use when unsure which documentation source to query or how to chain search-then-fetch tools for any package ecosystem.
---

# Using RTFD

RTFD provides 33 tools across 10 providers for real-time documentation lookup. Core pattern: **search first, then fetch full docs**.

## When to Use

- Need current docs for any library/package (PyPI, npm, crates.io, Go, Zig)
- Looking up package metadata, versions, or stats
- Browsing GitHub repos (tree, files, diffs, code search)
- Finding Docker images or inspecting Dockerfiles
- Querying GCP service documentation
- Writing LogScale/Humio queries (syntax, functions, operators)

## Quick Lookup

### Search (start here)

| Tool | Searches |
|------|----------|
| `search_library_docs` | **All ecosystems at once** (PyPI + npm + crates + GoDocs + GitHub) |
| `github_repo_search` | GitHub repositories (filter by language) |
| `github_code_search` | Code patterns (optionally scoped to repo) |
| `search_crates` | crates.io |
| `search_docker_images` | DockerHub |
| `search_gcp_services` | Google Cloud Platform services |
| `search_logscale_docs` | LogScale syntax, functions, operators |

### Metadata (quick info)

| Tool | Returns |
|------|---------|
| `pypi_metadata` | Version, URLs, project links |
| `npm_metadata` | Version, repository, maintainers |
| `crates_metadata` | Version, docs link, download stats |
| `godocs_metadata` | Package summary, source URL |
| `docker_image_metadata` | Stars, pulls, official status, tags |

### Fetch Full Docs

| Tool | Source |
|------|--------|
| `fetch_pypi_docs` | PyPI README (RST auto-converted to Markdown) |
| `fetch_npm_docs` | npm README |
| `fetch_godocs_docs` | godocs.io / pkg.go.dev |
| `fetch_gcp_service_docs` | cloud.google.com |
| `fetch_github_readme` | GitHub repo README |
| `fetch_docker_image_docs` | DockerHub README |
| `fetch_dockerfile` | Dockerfile from source repo (best-effort) |
| `zig_docs` | Official Zig language docs |

### GitHub Repo Exploration

| Tool | Purpose |
|------|---------|
| `get_repo_tree` | Full file tree (set `recursive=True`) |
| `list_repo_contents` | Directory listing at a path |
| `get_file_content` | Read a specific file (up to 100KB) |
| `get_commit_diff` | Diff between commits, branches, or tags |
| `list_github_packages` | GHCR packages for an owner |
| `get_package_versions` | Package version history |

### LogScale Query Reference

| Tool | Purpose |
|------|---------|
| `list_logscale_functions` | Browse functions by category |
| `logscale_syntax` | Syntax topic docs (filters, regex, time, macros...) |
| `logscale_function` | Single function signature and docs |

### Admin

| Tool | Purpose |
|------|---------|
| `get_cache_info` | Cache stats (entry count, size) |
| `get_cache_entries` | Detailed cache entries with age/preview |
| `get_next_chunk` | Retrieve next chunk when response was truncated |

## Common Workflows

**Library docs (any ecosystem):**
`search_library_docs("name")` → pick ecosystem → `fetch_pypi_docs` / `fetch_npm_docs` / etc.

**GitHub exploration:**
`github_repo_search("query")` → `get_repo_tree("owner/repo")` → `get_file_content("owner/repo", "path")`

**Docker investigation:**
`search_docker_images("query")` → `docker_image_metadata("image")` → `fetch_docker_image_docs("image")` → `fetch_dockerfile("image")`

**LogScale query help:**
`search_logscale_docs("topic")` → `logscale_syntax("topic")` or `logscale_function("name")`

## Key Details

- **Repo format**: Always `"owner/repo"` (e.g., `"psf/requests"`)
- **Chunking**: Large responses include a `continuation_token` — call `get_next_chunk` to get more
- **`max_bytes`**: All fetch tools accept this param (default 20480) to control response size
- **Caching**: Results cached for 1 week by default
- **`search_library_docs`** is the universal entry point — use ecosystem-specific tools only when you already know the ecosystem
