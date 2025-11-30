"""Tests for NPM provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from src.RTFD.providers.npm import NpmProvider
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a NPM provider instance."""
    return NpmProvider(create_http_client)


@pytest.fixture
def mock_npm_data():
    """Return mock NPM package data."""
    readme_content = "# Example Package\n\n" + ("Long content here. " * 10)
    return {
        "name": "example-pkg",
        "description": "An example package",
        "version": "1.0.0",
        "homepage": "https://example.com",
        "repository": {"type": "git", "url": "git+https://github.com/user/repo.git"},
        "license": "MIT",
        "readme": readme_content,
        "maintainers": [{"name": "User", "email": "user@example.com"}],
    }


def test_npm_metadata_structure(provider):
    """Test NPM provider metadata."""
    metadata = provider.get_metadata()
    assert metadata.name == "npm"
    assert metadata.supports_library_search is True
    assert "npm_metadata" in metadata.tool_names


@pytest.mark.asyncio
async def test_npm_search_success(provider, mock_npm_data):
    """Test successful search on NPM."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_npm_data
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    result = await provider.search_library("example-pkg")

    assert result.success is True
    assert result.data["name"] == "example-pkg"
    assert result.data["repository"] == "https://github.com/user/repo"  # cleaned url
    assert "Long content here" in result.data["readme"]


@pytest.mark.asyncio
async def test_npm_search_404(provider):
    """Test searching for non-existent package."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("404 Not Found", request=None, response=MagicMock(status_code=404))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    result = await provider.search_library("nonexistent")

    assert result.success is False
    assert result.error is None


@pytest.mark.asyncio
async def test_npm_metadata_tool(provider, mock_npm_data):
    """Test the npm_metadata tool."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_npm_data

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    tools = provider.get_tools()
    result = await tools["npm_metadata"]("example-pkg")

    assert result.content[0].type == "text"
    assert "example-pkg" in result.content[0].text


@pytest.mark.asyncio
async def test_fetch_npm_docs(provider, mock_npm_data):
    """Test fetching NPM docs (README)."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_npm_data
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    result = await provider._fetch_npm_docs("example-pkg")

    assert result["package"] == "example-pkg"
    assert "Example Package" in result["content"]
    assert result["source"] == "npm"


@pytest.mark.asyncio
async def test_fetch_npm_docs_minimal(provider, mock_npm_data):
    """Test fetching docs when README is empty/short."""
    mock_data = mock_npm_data.copy()
    mock_data["readme"] = ""  # Empty readme

    mock_response = MagicMock()
    mock_response.json.return_value = mock_data

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    result = await provider._fetch_npm_docs("example-pkg")

    assert result["source"] == "npm_minimal"
    assert "# example-pkg" in result["content"]
    assert "An example package" in result["content"]


@pytest.mark.asyncio
async def test_fetch_npm_docs_error(provider):
    """Test error handling in fetch_npm_docs."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("500 Error", request=None, response=MagicMock(status_code=500))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = NpmProvider(mock_factory)

    result = await provider._fetch_npm_docs("pkg")

    assert "error" in result
    assert "returned 500" in result["error"]
