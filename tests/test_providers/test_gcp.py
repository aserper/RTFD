"""Tests for GCP provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.RTFD.providers.gcp import GcpProvider, GCP_SERVICE_DOCS
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a GCP provider instance."""
    return GcpProvider(create_http_client)


def test_gcp_metadata():
    """Test GCP provider metadata."""
    provider = GcpProvider(lambda: None)
    metadata = provider.get_metadata()

    assert metadata.name == "gcp"
    assert metadata.expose_as_tool is True
    assert "search_gcp_services" in metadata.tool_names
    assert metadata.supports_library_search is True
    assert "GITHUB_TOKEN" in metadata.optional_env_vars


def test_gcp_get_tools():
    """Test that GCP provider provides correct tools."""
    provider = GcpProvider(lambda: None)
    tools = provider.get_tools()

    assert "search_gcp_services" in tools
    assert callable(tools["search_gcp_services"])


def test_gcp_normalize_service_name(provider):
    """Test service name normalization."""
    # Direct match
    assert provider._normalize_service_name("storage") == "storage"
    assert provider._normalize_service_name("compute") == "compute"

    # With prefixes
    assert provider._normalize_service_name("cloud storage") == "storage"
    assert provider._normalize_service_name("google cloud storage") == "storage"
    assert provider._normalize_service_name("gcp storage") == "storage"

    # Aliases
    assert provider._normalize_service_name("kubernetes") == "gke"
    assert provider._normalize_service_name("k8s") == "gke"
    assert provider._normalize_service_name("functions") == "cloudfunctions"
    assert provider._normalize_service_name("cloud functions") == "cloudfunctions"

    # Non-existent service
    assert provider._normalize_service_name("nonexistent-service") is None


@pytest.mark.asyncio
async def test_gcp_search_services_direct_match(provider):
    """Test searching for services with direct mapping match."""
    result = await provider._search_services("storage", limit=5)

    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["name"] == "Cloud Storage"
    assert result[0]["api"] == "storage.googleapis.com"
    assert result[0]["docs_url"] == "https://cloud.google.com/storage/docs"
    assert "source" in result[0]


@pytest.mark.asyncio
async def test_gcp_search_services_partial_match(provider):
    """Test searching for services with partial match."""
    # Mock cloud search to return empty so we test local mapping fallback
    with patch.object(provider, '_search_cloud_google_com', new_callable=AsyncMock) as mock_cloud:
        mock_cloud.return_value = []
        result = await provider._search_services("big", limit=5)
    
        assert isinstance(result, list)
        assert len(result) >= 1
        # Should match BigQuery and Bigtable
        service_names = [r["name"] for r in result]
        assert "BigQuery" in service_names or "Cloud Bigtable" in service_names


@pytest.mark.asyncio
async def test_gcp_search_services_normalized(provider):
    """Test searching with service name normalization."""
    result = await provider._search_services("cloud storage", limit=5)

    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["name"] == "Cloud Storage"


@pytest.mark.asyncio
async def test_gcp_search_library_success(provider):
    """Test library search integration."""
    result = await provider.search_library("storage", limit=5)

    assert result.success is True
    assert result.data is not None
    assert result.error is None
    assert result.provider_name == "gcp"
    assert isinstance(result.data, list)
    assert len(result.data) >= 1


@pytest.mark.asyncio
async def test_gcp_search_library_no_match(provider):
    """Test library search with no matches."""
    result = await provider.search_library("totally-unrelated-query-xyz", limit=5)

    # Should return empty results but not error
    assert result.success is True
    assert result.provider_name == "gcp"
    assert isinstance(result.data, list)


@pytest.mark.asyncio
async def test_gcp_search_github_failure_graceful(provider):
    """Test that GitHub API failures are handled gracefully."""
    # Mock the GitHub API to raise an exception
    with patch.object(provider, '_search_github_googleapis', side_effect=Exception("GitHub API error")):
        # Should still return results from local mapping
        result = await provider._search_services("storage", limit=5)
        assert isinstance(result, list)
        assert len(result) >= 1


@pytest.mark.asyncio
async def test_gcp_fetch_service_docs_known_service(provider):
    """Test fetching documentation for a known service."""
    # Mock the HTTP client to return fake HTML
    mock_html = """
    <html>
        <body>
            <main>
                <h1>Cloud Storage Documentation</h1>
                <p>Cloud Storage is a service for storing objects.</p>
                <h2>Quickstart</h2>
                <p>Get started with Cloud Storage.</p>
            </main>
        </body>
    </html>
    """

    # Create a mock response
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200

    # Create a mock client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # Mock the _http_client method
    provider._http_client = AsyncMock(return_value=mock_client)

    result = await provider._fetch_service_docs("storage", max_bytes=20480)

    assert result["service"] == "Cloud Storage"
    assert "content" in result
    assert len(result["content"]) > 0
    assert "Cloud Storage" in result["content"]
    assert result["source"] == "gcp_docs"
    assert result["docs_url"] == "https://cloud.google.com/storage/docs"
    assert "size_bytes" in result
    assert "truncated" in result


@pytest.mark.asyncio
async def test_gcp_fetch_service_docs_404(provider):
    """Test fetching documentation for non-existent service."""
    # Mock HTTP client to return 404
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=Exception("404 Not Found")
    )

    # Import httpx to use the actual exception
    import httpx
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=mock_response)
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    provider._http_client = AsyncMock(return_value=mock_client)

    result = await provider._fetch_service_docs("nonexistent-service", max_bytes=20480)

    assert result["service"] == "nonexistent-service"
    assert result["content"] == ""
    assert result["error"] == "Service documentation not found"
    assert result["size_bytes"] == 0
    assert result["source"] is None


@pytest.mark.asyncio
async def test_gcp_fetch_service_docs_truncation(provider):
    """Test that documentation is properly truncated when exceeding max_bytes."""
    # Create HTML with lots of content
    large_content = "<main>" + "<p>This is a paragraph. </p>" * 1000 + "</main>"
    mock_html = f"<html><body>{large_content}</body></html>"

    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    provider._http_client = AsyncMock(return_value=mock_client)

    max_bytes = 500
    result = await provider._fetch_service_docs("storage", max_bytes=max_bytes)

    assert result["size_bytes"] <= max_bytes + 100  # Allow some margin for section headers
    assert "content" in result


@pytest.mark.asyncio
async def test_gcp_search_services_tool(provider):
    """Test the search_gcp_services tool directly."""
    tools = provider.get_tools()
    tool = tools["search_gcp_services"]

    result = await tool("storage", limit=2)

    assert result.content[0].type == "text"
    text_content = result.content[0].text
    assert isinstance(text_content, str)
    assert "[" in text_content  # JSON array format
    assert "Cloud Storage" in text_content


@pytest.mark.asyncio
async def test_gcp_service_mapping_completeness():
    """Test that service mapping contains expected services."""
    required_services = [
        "storage", "compute", "bigquery", "cloudfunctions",
        "run", "pubsub", "firestore", "gke"
    ]

    for service in required_services:
        assert service in GCP_SERVICE_DOCS
        service_info = GCP_SERVICE_DOCS[service]
        assert "name" in service_info
        assert "url" in service_info
        assert "api" in service_info
        assert "description" in service_info


@pytest.mark.asyncio
async def test_gcp_fetch_with_normalized_name(provider):
    """Test fetching docs with various service name formats."""
    # Mock the HTTP response
    mock_html = "<html><body><main><h1>Test</h1><p>Content</p></main></body></html>"

    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    provider._http_client = AsyncMock(return_value=mock_client)

    # Test with different name formats
    for service_name in ["storage", "Cloud Storage", "cloud storage"]:
        result = await provider._fetch_service_docs(service_name, max_bytes=20480)
        assert result["service"] == "Cloud Storage"
        assert result["docs_url"] == "https://cloud.google.com/storage/docs"


def test_gcp_github_headers_without_token(provider):
    """Test GitHub headers generation without token."""
    import os
    # Temporarily remove token if it exists
    old_token = os.environ.pop("GITHUB_TOKEN", None)

    try:
        headers = provider._get_github_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "X-GitHub-Api-Version" in headers
        assert "Authorization" not in headers
    finally:
        # Restore token if it existed
        if old_token:
            os.environ["GITHUB_TOKEN"] = old_token


def test_gcp_github_headers_with_token(provider):
    """Test GitHub headers generation with token."""
    import os
    # Temporarily set a fake token
    old_token = os.environ.get("GITHUB_TOKEN")
    os.environ["GITHUB_TOKEN"] = "fake_token_123"

    try:
        headers = provider._get_github_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "token fake_token_123"
    finally:
        # Restore original state
        if old_token:
            os.environ["GITHUB_TOKEN"] = old_token
        else:
            os.environ.pop("GITHUB_TOKEN", None)
