"""Integration tests for npm provider using VCR cassettes."""

import pytest
from RTFD.providers.npm import NpmProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create npm provider instance."""
    return NpmProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_npm_search_library_react(provider):
    """Test searching for the 'react' package on real npm API."""
    result = await provider.search_library("react", limit=1)

    assert result.success is True
    assert result.provider_name == "npm"
    assert result.data is not None

    # Verify structure of real npm response
    assert "name" in result.data
    assert result.data["name"] == "react"
    assert "summary" in result.data
    assert "version" in result.data


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_npm_search_library_express(provider):
    """Test searching for the 'express' package."""
    result = await provider.search_library("express", limit=1)

    assert result.success is True
    assert result.data["name"] == "express"
    assert "summary" in result.data


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_npm_search_library_nonexistent(provider):
    """Test searching for a nonexistent npm package."""
    result = await provider.search_library("this-npm-package-definitely-does-not-exist-99999", limit=1)

    # npm returns 404 for nonexistent packages
    assert result.success is False
    assert result.provider_name == "npm"


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_npm_metadata_structure(provider):
    """Test that npm metadata contains all expected fields."""
    result = await provider.search_library("lodash", limit=1)

    assert result.success is True
    data = result.data

    # Validate critical fields
    expected_fields = ["name", "summary", "version"]
    for field in expected_fields:
        assert field in data, f"Missing expected field: {field}"

    # Validate types
    assert isinstance(data["name"], str)
    # version can be None for some packages, so just check it exists
    assert "version" in data
