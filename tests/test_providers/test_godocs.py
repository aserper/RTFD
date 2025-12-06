"""Tests for GoDocs provider."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

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


@pytest.fixture
def mock_html_with_docs():
    """Return mock HTML content with more detailed documentation."""
    return """
    <html>
        <head>
            <meta name="description" content="A Go package for testing">
        </head>
        <body>
            <h2 id="pkg-overview">Overview</h2>
            <p>import "github.com/user/package"</p>
            <p>Package testing provides support for automated testing of Go packages.</p>
            <div id="main" class="main">
                <h2>Functions</h2>
                <p>func TestExample(t *testing.T)</p>
                <p>TestExample tests basic functionality.</p>
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
    # fetch_godocs_docs should be included when fetch is enabled
    assert "fetch_godocs_docs" in metadata.tool_names


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
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=None, response=MagicMock(status_code=404)
    )
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
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=None, response=MagicMock(status_code=500)
    )
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


@pytest.mark.asyncio
async def test_fetch_godocs_docs_success(mock_html_with_docs):
    """Test successful fetching of GoDocs documentation."""
    mock_response = MagicMock()
    mock_response.text = mock_html_with_docs

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider._fetch_godocs_docs("github.com/user/package")

    assert result["package"] == "github.com/user/package"
    assert result["content"] != ""
    assert "Package testing" in result["content"]
    assert result["source"] == "godocs"
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_fetch_godocs_docs_with_max_bytes(mock_html_with_docs):
    """Test documentation fetching with byte limit."""
    mock_response = MagicMock()
    mock_response.text = mock_html_with_docs

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider._fetch_godocs_docs("github.com/user/package", max_bytes=50)

    assert result["package"] == "github.com/user/package"
    assert result["size_bytes"] <= 50
    assert result["source"] == "godocs"


@pytest.mark.asyncio
async def test_fetch_godocs_docs_404(provider):
    """Test fetching docs for non-existent package."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=None, response=MagicMock(status_code=404)
    )
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    result = await provider._fetch_godocs_docs("nonexistent")

    assert result["package"] == "nonexistent"
    assert result["content"] == ""
    assert result["error"] == "Package not found on GoDocs"
    assert result["source"] is None


@pytest.mark.asyncio
async def test_fetch_godocs_docs_tool(mock_html_with_docs):
    """Test the fetch_godocs_docs tool."""
    mock_response = MagicMock()
    mock_response.text = mock_html_with_docs

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = GoDocsProvider(mock_factory)

    tools = provider.get_tools()
    assert "fetch_godocs_docs" in tools

    result = await tools["fetch_godocs_docs"]("github.com/user/package")

    assert result.content[0].type == "text"
    assert "github.com/user/package" in result.content[0].text
    assert "Package testing" in result.content[0].text
