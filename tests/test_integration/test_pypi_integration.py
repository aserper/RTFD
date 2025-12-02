"""Integration tests for PyPI provider using VCR cassettes.

These tests use pytest-recording to record real API responses to cassettes.
On first run with --record-mode=once, they hit the real PyPI API.
On subsequent runs, they replay recorded responses for fast, deterministic tests.

To record/update cassettes:
    pytest tests/test_integration/test_pypi_integration.py --record-mode=rewrite

To run without network access (using existing cassettes):
    pytest tests/test_integration/test_pypi_integration.py
"""

import pytest
from RTFD.providers.pypi import PyPIProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create PyPI provider instance."""
    return PyPIProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_pypi_search_library_requests_package(provider):
    """Test searching for the 'requests' package on real PyPI API."""
    result = await provider.search_library("requests", limit=1)

    assert result.success is True
    assert result.provider_name == "pypi"
    assert result.data is not None

    # Verify structure of real PyPI response
    assert "name" in result.data
    assert result.data["name"] == "requests"
    assert "summary" in result.data
    assert "version" in result.data
    assert "home_page" in result.data or "project_urls" in result.data


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_pypi_search_library_httpx_package(provider):
    """Test searching for the 'httpx' package."""
    result = await provider.search_library("httpx", limit=1)

    assert result.success is True
    assert result.data["name"] == "httpx"
    assert "summary" in result.data
    assert "version" in result.data


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_pypi_search_library_nonexistent_package(provider):
    """Test searching for a package that doesn't exist."""
    result = await provider.search_library("this-package-definitely-does-not-exist-12345", limit=1)

    # PyPI returns 404 for nonexistent packages
    assert result.success is False
    assert result.provider_name == "pypi"
    assert "404" in str(result.error) or "Not Found" in str(result.error)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_pypi_metadata_structure(provider):
    """Test that PyPI metadata contains all expected fields."""
    result = await provider.search_library("pytest", limit=1)

    assert result.success is True
    data = result.data

    # Validate all critical fields exist in real API response
    expected_fields = ["name", "summary", "version"]
    for field in expected_fields:
        assert field in data, f"Missing expected field: {field}"

    # Validate types
    assert isinstance(data["name"], str)
    assert isinstance(data["summary"], str)
    assert isinstance(data["version"], str)
