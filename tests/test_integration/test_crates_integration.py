"""Integration tests for Rust Crates provider using VCR cassettes."""

import pytest
from RTFD.providers.crates import CratesProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create Crates provider instance."""
    return CratesProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_crates_search_library_serde(provider):
    """Test searching for 'serde' on crates.io."""
    result = await provider.search_library("serde", limit=1)

    assert result.success is True
    assert result.provider_name == "crates"
    assert result.data is not None

    # Verify structure - should return dict with 'results' key
    assert isinstance(result.data, dict)
    assert "results" in result.data
    results = result.data["results"]
    if len(results) > 0:
        crate = results[0]
        assert "name" in crate
        assert crate["name"] == "serde"


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_crates_search_library_tokio(provider):
    """Test searching for 'tokio' async runtime."""
    result = await provider.search_library("tokio", limit=1)

    assert result.success is True
    assert isinstance(result.data, dict)
    assert "results" in result.data
    if len(result.data["results"]) > 0:
        assert result.data["results"][0]["name"] == "tokio"


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_crates_search_structure(provider):
    """Test that crates.io search returns expected structure."""
    result = await provider.search_library("rand", limit=2)

    assert result.success is True
    assert isinstance(result.data, dict)
    assert "results" in result.data

    results = result.data["results"]
    if len(results) > 0:
        crate = results[0]
        # Validate common fields from crates.io API
        expected_fields = ["name"]
        for field in expected_fields:
            assert field in crate, f"Missing expected field: {field}"
