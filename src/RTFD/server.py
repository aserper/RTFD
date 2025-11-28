"""
MCP gateway server that surfaces library documentation by querying Google, GitHub, PyPI, and GoDocs.

The server uses a pluggable provider architecture with auto-discovery. Providers are loaded
from the providers/ directory and can optionally expose individual MCP tools or participate
in the aggregated search_library_docs tool.
"""

from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from .providers import discover_providers
from .providers.base import BaseProvider
from .utils import create_http_client, serialize_response

# Initialize FastMCP server
mcp = FastMCP("rtfd-gateway")

# Provider instances (initialized on first use)
_provider_instances: Dict[str, BaseProvider] = {}


def _get_provider_instances() -> Dict[str, BaseProvider]:
    """
    Get or create provider instances.

    Lazy initialization of providers with shared HTTP client factory.
    """
    if _provider_instances:
        return _provider_instances

    provider_classes = discover_providers()

    for name, provider_class in provider_classes.items():
        try:
            instance = provider_class(create_http_client)
            _provider_instances[name] = instance
        except Exception as e:
            # Log but don't crash - defensive initialization
            print(f"Warning: Failed to initialize provider {name}: {e}")

    return _provider_instances


def _register_provider_tools() -> None:
    """
    Discover and register all provider tools with FastMCP.

    This function is called once at module initialization to dynamically
    register all tools from providers that opt-in via expose_as_tool=True.
    """
    providers = _get_provider_instances()

    for provider_name, provider in providers.items():
        metadata = provider.get_metadata()

        # Skip providers that don't want individual tool exposure
        if not metadata.expose_as_tool:
            continue

        # Get tool functions from provider
        tools = provider.get_tools()

        # Register each tool with FastMCP
        for tool_name, tool_fn in tools.items():
            # Extract description from docstring
            description = tool_fn.__doc__ or f"{provider_name} tool"

            # Wrap the tool function to ensure it's properly decorated
            decorated_tool = mcp.tool(description=description)(tool_fn)


async def _locate_library_docs(library: str, limit: int = 5) -> Dict[str, Any]:
    """
    Try to find documentation links for a given library using all available providers.

    This is the aggregator function that combines results from PyPI, GoDocs, GitHub, and Google.
    """
    result: Dict[str, Any] = {"library": library}
    providers = _get_provider_instances()

    # Query each provider that supports library search
    for provider_name, provider in providers.items():
        metadata = provider.get_metadata()

        if not metadata.supports_library_search:
            continue

        provider_result = await provider.search_library(library, limit=limit)

        if provider_result.success:
            # Success: add data to result
            # Map provider name to appropriate result key
            key_mapping = {
                "pypi": "pypi",
                "godocs": "godocs",
                "github": "github_repos",
                "google": "web",
            }
            result_key = key_mapping.get(provider_name, provider_name)
            result[result_key] = provider_result.data
        elif provider_result.error:
            # Error: add error message (skip if error is None - silent fail)
            error_key = f"{provider_name}_error"
            result[error_key] = provider_result.error

    return result


@mcp.tool(
    description="Find docs for a library using PyPI metadata, GitHub repos, and Google search combined. Returns data in TOON format."
)
async def search_library_docs(library: str, limit: int = 5) -> str:
    """Aggregated library documentation search across all providers."""
    result = await _locate_library_docs(library, limit=limit)
    return serialize_response(result)


# Auto-register all provider tools
_register_provider_tools()


def run() -> None:
    """Entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    run()
