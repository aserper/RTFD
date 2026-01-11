# RTFD as a Claude Code Plugin

This document explains how to use RTFD as a Claude Code plugin to enable real-time documentation access within Claude Code.

## Installation

### Step 1: Add the RTFD Plugin Marketplace

First, add the RTFD repository as a Claude Code plugin marketplace:

```bash
claude plugin marketplace add aserper/RTFD
```

Or with a full GitHub URL:

```bash
claude plugin marketplace add https://github.com/aserper/RTFD
```

### Step 2: Install the Plugin

Once the marketplace is added, install the RTFD plugin:

```bash
claude plugin install rtfd-mcp@rtfd-marketplace
```

### Alternative: Local Installation (For Development)

If you're developing locally, you can add a local marketplace:

```bash
claude plugin marketplace add /path/to/RTFD
```

Then install:

```bash
claude plugin install rtfd-mcp
```

### Alternative: Manual Configuration

If you prefer to configure it manually, add the following to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "extraKnownMarketplaces": {
    "rtfd-marketplace": {
      "source": {
        "source": "github",
        "repo": "aserper/RTFD"
      }
    }
  },
  "enabledPlugins": {
    "rtfd-mcp@rtfd-marketplace": true
  }
}
```

## Configuration

Once installed, you can configure RTFD behavior through environment variables:

- **RTFD_FETCH** (default: `true`): Enable/disable content fetching. Set to `false` to allow only metadata lookups.
- **VERIFIED_BY_PYPI** (default: `false`): When enabled, restrict Python package documentation to PyPI-verified sources only.
- **GITHUB_AUTH** (default: `false`): Enable GitHub authentication for higher API rate limits.
- **GITHUB_TOKEN**: GitHub personal access token for authenticated requests (optional but recommended).

Example configuration in Claude Code:

```json
{
  "plugins": [
    {
      "name": "rtfd-mcp",
      "env": {
        "RTFD_FETCH": "true",
        "VERIFIED_BY_PYPI": "false",
        "GITHUB_AUTH": "false",
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  ]
}
```

## Supported Documentation Sources

RTFD provides access to documentation from multiple package ecosystems:

- **Python**: PyPI packages
- **JavaScript/TypeScript**: npm packages
- **Rust**: crates.io
- **Go**: GoDocs
- **Zig**: Official Zig documentation
- **Docker**: DockerHub images
- **GitHub**: Container Registry (GHCR) and repositories
- **Cloud**: Google Cloud Platform (GCP) services

## Features

### Documentation Fetching
Retrieve full documentation content from PyPI, npm, and GitHub repositories, with automatic extraction of relevant sections like:
- Installation instructions
- Usage examples
- API references
- Quickstart guides

### Metadata Queries
Quick lookups for available versions, popularity metrics, and other package metadata.

### Format Conversion
Automatic conversion of reStructuredText and HTML to Markdown for consistent formatting.

### GitHub Repository Browsing
- List repository file trees
- Browse directory structures
- Read source code files directly

### Smart Content Extraction
Intelligently extracts the most relevant sections from documentation to reduce noise and provide exactly what you need.

## Usage Examples

Once installed, RTFD automatically becomes available to Claude Code agents and can be used to:

- **Fetch library documentation**: Get the latest API docs for a library you're working with
- **Version checking**: Find available versions and upgrade guides
- **Integration help**: Look up exact syntax and examples for unfamiliar libraries
- **Dependency audits**: Check multiple package registries for updates

## Security Considerations

⚠️ **Important**: RTFD grants access to unverified content from external sources (GitHub, PyPI, etc.). This introduces risks including:
- Indirect prompt injection attacks
- Potential malicious code in documentation

**Mitigation strategies:**
- Set `RTFD_FETCH=false` to disable content fetching and allow only metadata lookups
- Enable `VERIFIED_BY_PYPI=true` to restrict Python packages to verified sources
- Use read-only GitHub tokens with minimal permissions
- Review content before acting on it

## Support

For issues, questions, or contributions, visit the [RTFD GitHub repository](https://github.com/aserper/RTFD).

## License

RTFD is released under the MIT License. See the LICENSE file for details.
