"""Tests for Zig provider."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from bs4 import BeautifulSoup

from src.RTFD.providers.zig import ZigProvider
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a Zig provider instance."""
    return ZigProvider(create_http_client)


@pytest.fixture
def mock_html_content():
    """Return mock HTML content for Zig documentation."""
    return """
    <html>
        <body>
            <h1>Zig Documentation</h1>
            <p>Welcome to Zig docs.</p>

            <h2>Installation</h2>
            <p>How to install Zig.</p>

            <h2>Language Reference</h2>
            <p>Details about the language.</p>

            <h3>Variables</h3>
            <p>const and var keywords.</p>

            <h3>Functions</h3>
            <p>fn keyword usage.</p>
        </body>
    </html>
    """


def test_zig_metadata(provider):
    """Test Zig provider metadata."""
    metadata = provider.get_metadata()
    assert metadata.name == "zig"
    assert metadata.supports_library_search is False
    assert "zig_docs" in metadata.tool_names


@pytest.mark.asyncio
async def test_zig_search_library_not_supported(provider):
    """Test that search_library returns failure as it's not supported."""
    result = await provider.search_library("anything")
    assert result.success is False
    assert "not support" in result.error


@pytest.mark.asyncio
async def test_zig_docs_search_success(provider, mock_html_content):
    """Test successful search in Zig docs."""

    # Mock HTTP client response
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # The factory needs to return an awaitable that yields the client
    # In base.py: return await self._http_client_factory()

    async def mock_factory():
        return mock_client

    provider = ZigProvider(mock_factory)

    # Test the internal search method
    result = await provider._search_zig_docs("variables")

    # Debug info if fails
    if "error" in result:
        print(f"DEBUG: {result['error']}")

    assert result["query"] == "variables"
    assert "matches" in result
    matches = result["matches"]
    assert len(matches) > 0
    assert matches[0]["title"] == "Variables"
    assert "const and var" in matches[0]["summary"]


@pytest.mark.asyncio
async def test_zig_docs_search_tool(provider, mock_html_content):
    """Test the zig_docs tool."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = ZigProvider(mock_factory)

    tools = provider.get_tools()
    assert "zig_docs" in tools

    # Run the tool
    result = await tools["zig_docs"]("install")

    assert result.content[0].type == "text"
    text = result.content[0].text
    assert "Installation" in text
    assert "How to install Zig" in text


@pytest.mark.asyncio
async def test_zig_docs_http_error(provider):
    """Test handling of HTTP errors."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.HTTPStatusError("404 Not Found", request=None, response=None)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = ZigProvider(mock_factory)

    result = await provider._search_zig_docs("query")

    assert "error" in result
    assert "Failed to fetch" in result["error"]


@pytest.mark.asyncio
async def test_zig_docs_general_error(provider):
    """Test handling of general exceptions."""
    async def mock_factory():
        raise Exception("Something bad")

    provider = ZigProvider(mock_factory)

    result = await provider._search_zig_docs("query")

    assert "error" in result
    assert "Error searching" in result["error"]


def test_extract_doc_sections(provider, mock_html_content):
    """Test extracting sections from HTML."""
    soup = BeautifulSoup(mock_html_content, "html.parser")
    sections = provider._extract_doc_sections(soup)

    assert len(sections) == 5  # H1, H2, H2, H3, H3

    # Check Installation section
    install = next(s for s in sections if s["title"] == "Installation")
    assert install["summary"] == "How to install Zig."

    # Check Variables section
    variables = next(s for s in sections if s["title"] == "Variables")
    assert "const and var" in variables["summary"]


def test_search_sections(provider):
    """Test scoring and sorting of sections."""
    sections = [
        {"title": "Installation", "summary": "Setup guide"},
        {"title": "Variables", "summary": "const var"},
        {"title": "Functions", "summary": "fn keyword"},
        {"title": "Values", "summary": "const values"},
    ]

    # Search for "var"
    # Variables: match in title (2 pts) + match in summary (1 pt) = 3
    # Values: match in summary? No ("values" != "var")?
    # Logic is `word in string` or `string.count(word)`?
    # Code uses `title_lower.count(word)`. "var" is in "variables".

    matches = provider._search_sections(sections, "var")

    assert len(matches) > 0
    assert matches[0]["title"] == "Variables"
    # "Values" summary has "values". "values".count("var") -> 0?
    # "values" contains "v", "a", "l"... no.
    # But "var" is a substring of "variable".
    # Wait, code: `title_lower.count(word)`.
    # "variables".count("var") -> 1.

    # Check multiple words
    matches = provider._search_sections(sections, "setup guide")
    assert matches[0]["title"] == "Installation"
