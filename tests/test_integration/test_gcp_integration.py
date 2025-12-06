"""Integration tests for GCP provider using VCR cassettes.

These tests use pytest-recording to record real API responses to cassettes.
On first run with --record-mode=once, they hit the real GCP docs and GitHub API.
On subsequent runs, they replay recorded responses for fast, deterministic tests.

To record/update cassettes:
    pytest tests/test_integration/test_gcp_integration.py --record-mode=rewrite

To run without network access (using existing cassettes):
    pytest tests/test_integration/test_gcp_integration.py

Note: GitHub API calls may require GITHUB_TOKEN for higher rate limits.
"""

import pytest

from RTFD.providers.gcp import GcpProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create GCP provider instance."""
    return GcpProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_storage_service(provider):
    """Test searching for Cloud Storage service."""
    result = await provider.search_library("storage", limit=5)

    assert result.success is True
    assert result.provider_name == "gcp"
    assert result.data is not None
    assert isinstance(result.data, list)
    assert len(result.data) > 0

    # Verify structure of response
    first_result = result.data[0]
    assert "name" in first_result
    assert "description" in first_result
    assert "api" in first_result
    assert "docs_url" in first_result

    # Should match Cloud Storage
    assert "Storage" in first_result["name"]


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_compute_service(provider):
    """Test searching for Compute Engine service."""
    result = await provider.search_library("compute", limit=5)

    assert result.success is True
    assert result.data is not None
    assert len(result.data) > 0

    # Should find Compute Engine
    service_names = [s["name"] for s in result.data]
    assert "Compute Engine" in service_names


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_bigquery_service(provider):
    """Test searching for BigQuery service."""
    result = await provider.search_library("bigquery", limit=5)

    assert result.success is True
    assert result.data is not None
    assert len(result.data) > 0

    first_result = result.data[0]
    assert first_result["name"] == "BigQuery"
    assert "bigquery" in first_result["api"]


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_kubernetes_alias(provider):
    """Test searching with Kubernetes alias for GKE."""
    result = await provider.search_library("kubernetes", limit=5)

    assert result.success is True
    assert result.data is not None
    assert len(result.data) > 0

    # Should resolve to GKE
    first_result = result.data[0]
    assert "Kubernetes" in first_result["name"]


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_with_prefix(provider):
    """Test searching with 'cloud' prefix."""
    result = await provider.search_library("cloud storage", limit=5)

    assert result.success is True
    assert result.data is not None
    assert len(result.data) > 0

    # Should still find Cloud Storage
    first_result = result.data[0]
    assert "Storage" in first_result["name"]


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_partial_match(provider):
    """Test searching with partial match."""
    result = await provider.search_library("function", limit=5)

    assert result.success is True
    assert result.data is not None
    assert len(result.data) > 0

    # Should find Cloud Functions
    service_names = [s["name"] for s in result.data]
    assert "Cloud Functions" in service_names


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_library_no_match(provider):
    """Test searching for something that doesn't match GCP services."""
    result = await provider.search_library("totally-unrelated-service-xyz", limit=5)

    # Should succeed but return empty or minimal results
    assert result.success is True
    assert result.provider_name == "gcp"
    assert isinstance(result.data, list)
    # May be empty or have fallback results


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_services_direct(provider):
    """Test direct search_services method."""
    result = await provider._search_services("pubsub", limit=3)

    assert isinstance(result, list)
    assert len(result) > 0

    # Should find Pub/Sub
    first_result = result[0]
    assert "Pub/Sub" in first_result["name"]
    assert "pubsub" in first_result["api"]
    assert "docs_url" in first_result


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_search_multiple_results(provider):
    """Test that search can return multiple relevant results."""
    result = await provider._search_services("cloud", limit=5)

    assert isinstance(result, list)
    # "cloud" is a common term, should match multiple services
    assert len(result) >= 3


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gcp_service_metadata_completeness(provider):
    """Test that service results have all required fields."""
    result = await provider._search_services("storage", limit=1)

    assert len(result) > 0
    service = result[0]

    required_fields = ["name", "description", "api", "docs_url", "source"]
    for field in required_fields:
        assert field in service, f"Missing required field: {field}"

    # Validate types
    assert isinstance(service["name"], str)
    assert isinstance(service["description"], str)
    assert isinstance(service["api"], str)
    assert isinstance(service["docs_url"], str)


# Note: fetch_gcp_service_docs tests are commented out because they require
# scraping live GCP documentation pages which may change frequently and could
# cause test instability. These tests should be run manually during development.

# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_gcp_fetch_service_docs_storage(provider):
#     """Test fetching documentation for Cloud Storage."""
#     result = await provider._fetch_service_docs("storage", max_bytes=20480)
#
#     assert result["service"] == "Cloud Storage"
#     assert len(result["content"]) > 0
#     assert result["source"] == "gcp_docs"
#     assert result["docs_url"] == "https://cloud.google.com/storage/docs"
#     assert "size_bytes" in result
#     assert result["size_bytes"] > 0


# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_gcp_fetch_service_docs_compute(provider):
#     """Test fetching documentation for Compute Engine."""
#     result = await provider._fetch_service_docs("compute", max_bytes=20480)
#
#     assert result["service"] == "Compute Engine"
#     assert len(result["content"]) > 0
#     assert "Compute Engine" in result["content"]


# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_gcp_fetch_service_docs_nonexistent(provider):
#     """Test fetching documentation for non-existent service."""
#     result = await provider._fetch_service_docs("nonexistent-service-xyz", max_bytes=20480)
#
#     assert result["service"] == "nonexistent-service-xyz"
#     # Should handle gracefully
#     assert "error" in result or len(result["content"]) >= 0
