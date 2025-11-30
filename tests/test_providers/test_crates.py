"""Tests for Crates provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest
import httpx

from src.RTFD.providers.crates import CratesProvider
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a Crates provider instance."""
    return CratesProvider(create_http_client)


@pytest.fixture
def mock_crates_search_response():
    """Return mock crates.io search response."""
    return {
        "crates": [
            {
                "name": "serde",
                "max_version": "1.0.197",
                "description": "A generic serialization/deserialization framework",
                "repository": "https://github.com/serde-rs/serde",
                "documentation": "https://docs.rs/serde",
                "downloads": 1000000,
            }
        ],
        "meta": {"total": 1}
    }


@pytest.fixture
def mock_crate_metadata_response():
    """Return mock crates.io crate metadata response."""
    return {
        "crate": {
            "name": "serde",
            "max_version": "1.0.197",
            "description": "A generic serialization/deserialization framework",
            "repository": "https://github.com/serde-rs/serde",
            "documentation": "https://docs.rs/serde",
            "downloads": 1000000,
            "categories": ["encoding"],
            "keywords": ["json"],
        },
        "versions": [{"license": "MIT OR Apache-2.0", "rust_version": "1.31"}]
    }


def test_crates_metadata_structure(provider):
    """Test Crates provider metadata."""
    metadata = provider.get_metadata()
    assert metadata.name == "crates"
    assert metadata.supports_library_search is True
    assert "crates_metadata" in metadata.tool_names
    assert "search_crates" in metadata.tool_names


@pytest.mark.asyncio
async def test_crates_search_success(provider, mock_crates_search_response):
    """Test successful search on crates.io."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_crates_search_response
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = CratesProvider(mock_factory)

    result = await provider.search_library("serde")

    assert result.success is True
    assert result.data["query"] == "serde"
    assert len(result.data["results"]) == 1
    assert result.data["results"][0]["name"] == "serde"
    assert result.data["results"][0]["version"] == "1.0.197"


@pytest.mark.asyncio
async def test_crates_metadata_tool(provider, mock_crate_metadata_response):
    """Test the crates_metadata tool."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_crate_metadata_response
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = CratesProvider(mock_factory)

    tools = provider.get_tools()
    result = await tools["crates_metadata"]("serde")

    assert result.content[0].type == "text"
    assert "serde" in result.content[0].text
    assert "1.0.197" in result.content[0].text
    assert "encoding" in result.content[0].text


@pytest.mark.asyncio
async def test_crates_search_tool(provider, mock_crates_search_response):
    """Test the search_crates tool."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_crates_search_response

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = CratesProvider(mock_factory)

    tools = provider.get_tools()
    result = await tools["search_crates"]("serde")

    assert result.content[0].type == "text"
    assert "serde" in result.content[0].text


@pytest.mark.asyncio
async def test_crates_http_error(provider):
    """Test handling of HTTP errors."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("500 Error", request=None, response=MagicMock(status_code=500))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = CratesProvider(mock_factory)

    # We patch _search_crates to simulate an exception that propagates to search_library
    # This is necessary because _search_crates handles exceptions internally, but we want
    # to test search_library's error handling for other potential failures.
    with patch.object(provider, '_search_crates', side_effect=httpx.HTTPStatusError("500 Error", request=None, response=MagicMock(status_code=500))):
         result = await provider.search_library("error")
         assert result.success is False
         assert "returned 500" in result.error


@pytest.mark.asyncio
async def test_crates_rate_limiting(provider, mock_crates_search_response):
    """Test that rate limiting sleeps appropriately."""
    mock_response = MagicMock()
    mock_response.json.return_value = mock_crates_search_response

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = CratesProvider(mock_factory)

    # Mock asyncio.sleep to verify it's called
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Manually set last request time to now to force a wait
        provider._last_request_time = time.time()

        await provider.search_library("serde")

        # Should have called sleep because we just set the time
        mock_sleep.assert_called_once()
