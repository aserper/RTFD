"""Tests for PyPI provider."""

import pytest

from src.RTFD.providers.pypi import PyPIProvider
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a PyPI provider instance."""
    return PyPIProvider(create_http_client)


def test_pypi_metadata():
    """Test PyPI provider metadata."""
    provider = PyPIProvider(lambda: None)
    metadata = provider.get_metadata()

    assert metadata.name == "pypi"
    assert metadata.expose_as_tool is True
    assert "pypi_metadata" in metadata.tool_names
    assert metadata.supports_library_search is True


def test_pypi_get_tools():
    """Test that PyPI provider provides correct tools."""
    provider = PyPIProvider(lambda: None)
    tools = provider.get_tools()

    assert "pypi_metadata" in tools
    assert callable(tools["pypi_metadata"])


@pytest.mark.asyncio
async def test_pypi_search_library_success(provider):
    """Test successful library search on PyPI."""
    result = await provider.search_library("requests", limit=5)

    assert result.success is True
    assert result.data is not None
    assert result.error is None
    assert result.provider_name == "pypi"
    assert result.data["name"] == "requests"
    assert "version" in result.data
    assert "summary" in result.data


@pytest.mark.asyncio
async def test_pypi_search_library_not_found(provider):
    """Test searching for non-existent package on PyPI."""
    result = await provider.search_library("nonexistent-package-xyz-123", limit=5)

    assert result.success is False
    assert result.data is None
    assert result.error is not None
    assert "404" in result.error
    assert result.provider_name == "pypi"


@pytest.mark.asyncio
async def test_pypi_fetch_metadata_structure(provider):
    """Test that fetched metadata has correct structure."""
    metadata = await provider._fetch_metadata("requests")

    required_fields = ["name", "summary", "version", "home_page", "docs_url", "project_urls"]
    for field in required_fields:
        assert field in metadata


@pytest.mark.asyncio
async def test_pypi_metadata_tool(provider):
    """Test the pypi_metadata tool directly."""
    tools = provider.get_tools()
    tool = tools["pypi_metadata"]

    result = await tool("requests")

    assert result.content[0].type == "text"
    text_content = result.content[0].text
    assert isinstance(text_content, str)
    assert "requests" in text_content  # Should contain package name
    assert "2." in text_content  # Should contain version number
    assert "{" in text_content  # Should be JSON
