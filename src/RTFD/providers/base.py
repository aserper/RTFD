"""Base provider interface and metadata classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ProviderMetadata:
    """Metadata describing a provider's capabilities and configuration."""

    # Identity
    name: str  # e.g., "pypi", "github"
    description: str  # Human-readable description

    # MCP tool exposure control
    expose_as_tool: bool = True  # If False, only available through aggregator
    tool_names: list[str] = field(default_factory=list)  # Tool names to register

    # Aggregator integration
    supports_library_search: bool = False  # Can participate in search_library_docs

    # Configuration
    required_env_vars: list[str] = field(default_factory=list)  # e.g., ["GITHUB_TOKEN"]
    optional_env_vars: list[str] = field(default_factory=list)


@dataclass
class ProviderResult:
    """Standardized result from a provider operation."""

    success: bool
    data: Any | None = None  # Dict or List for successful results
    error: str | None = None  # Error message if failed
    provider_name: str = ""  # Name of provider that generated this result


class BaseProvider(ABC):
    """Abstract base class for all documentation providers."""

    def __init__(self, http_client_factory: Callable[[], Awaitable[httpx.AsyncClient]]):
        """
        Initialize provider with HTTP client factory.

        Args:
            http_client_factory: Async function that returns configured httpx.AsyncClient
        """
        self._http_client_factory = http_client_factory

    @abstractmethod
    def get_metadata(self) -> ProviderMetadata:
        """Return provider metadata for auto-discovery and registration."""
        pass

    @abstractmethod
    async def search_library(self, library: str, limit: int = 5) -> ProviderResult:
        """
        Search for library documentation (for aggregator integration).

        Only called if supports_library_search=True in metadata.

        Args:
            library: Library/package name to search for
            limit: Maximum number of results to return

        Returns:
            ProviderResult with data or error
        """
        pass

    def get_tools(self) -> dict[str, Callable]:
        """
        Return dict of tool_name -> async_function for MCP registration.

        Only called if expose_as_tool=True in metadata.
        Each function should return serialized string.

        Returns:
            Dict mapping tool names to async callable functions
        """
        return {}

    async def _http_client(self) -> httpx.AsyncClient:
        """Get configured HTTP client instance."""
        return await self._http_client_factory()
