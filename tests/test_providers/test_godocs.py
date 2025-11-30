"""Tests for GoDocs provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx

from src.RTFD.providers.godocs import GoDocsProvider
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a GoDocs provider instance."""
    return GoDocsProvider(create_http_client)


@pytest.fixture
def mock_html_content():
    """Return mock HTML content for GoDocs page."""
    return """
    <html>
        <head>
            <meta name="description" content="A Go package for testing">
        </head>
        <body>
            <div id="pkg-overview">
                <h3>Overview</h3>
                <p>import "github.com/user/package"</p>
                <p>Package testing provides support for automated testing of Go packages.</p>
            </div>
        </body>
    </html>
    """


def test_godocs_metadata_structure(provider):
    """Test GoDocs provider metadata."""
    metadata = provider.get_metadata()
    assert metadata.name == "godocs"
    assert metadata.supports_library_search is True
    assert "godocs_metadata" in metadata.tool_names


@pytest.mark.asyncio
async def test_godocs_search_success(provider, mock_html_content):
    """Test successful search on GoDocs."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider.search_library("github.com/user/package")

    assert result.success is True
    assert result.data["name"] == "github.com/user/package"
    assert result.data["summary"] == "A Go package for testing"
    assert result.data["url"] == "https://godocs.io/github.com/user/package"


@pytest.mark.asyncio
async def test_godocs_search_404(provider):
    """Test searching for non-existent package (returns success=False but no error)."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("404 Not Found", request=None, response=MagicMock(status_code=404))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider.search_library("nonexistent")

    assert result.success is False
    assert result.error is None  # Should not be an error for 404


@pytest.mark.asyncio
async def test_godocs_search_http_error(provider):
    """Test searching with other HTTP errors."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("500 Server Error", request=None, response=MagicMock(status_code=500))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider.search_library("error-package")

    assert result.success is False
    assert result.error is not None
    assert "returned 500" in result.error


@pytest.mark.asyncio
async def test_godocs_metadata_tool(provider, mock_html_content):
    """Test the godocs_metadata tool."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    tools = provider.get_tools()
    result = await tools["godocs_metadata"]("github.com/user/package")

    assert result.content[0].type == "text"
    assert "github.com/user/package" in result.content[0].text
    assert "A Go package for testing" in result.content[0].text


@pytest.mark.asyncio
async def test_godocs_fallback_description(provider):
    """Test extracting description from body when meta description is missing."""
    html_no_meta = """
    <html>
        <body>
            <h2 id="pkg-overview">Overview</h2>
            <p>import "pkg"</p>
            <p>This is the fallback description.</p>
        </body>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_no_meta

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    data = await provider._fetch_metadata("pkg")
    assert data["summary"] == "This is the fallback description."
