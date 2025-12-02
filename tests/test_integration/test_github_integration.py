"""Integration tests for GitHub provider using VCR cassettes."""

import pytest
from RTFD.providers.github import GitHubProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create GitHub provider instance."""
    return GitHubProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_github_search_library_requests(provider):
    """Test searching for 'requests' on GitHub."""
    result = await provider.search_library("requests", limit=1)

    assert result.success is True
    assert result.provider_name == "github"
    assert result.data is not None

    # Verify structure - should return list of repo results
    assert isinstance(result.data, list)
    if len(result.data) > 0:
        repo = result.data[0]
        assert "name" in repo
        assert "description" in repo or repo.get("description") is None


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_github_search_library_python(provider):
    """Test searching for Python-related repos."""
    result = await provider.search_library("fastapi", limit=1)

    assert result.success is True
    assert isinstance(result.data, list)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_github_repo_search_structure(provider):
    """Test that GitHub repo search returns expected structure."""
    result = await provider.search_library("django", limit=2)

    assert result.success is True
    assert isinstance(result.data, list)

    if len(result.data) > 0:
        repo = result.data[0]
        # Validate common fields from GitHub API
        expected_fields = ["name"]
        for field in expected_fields:
            assert field in repo, f"Missing expected field: {field}"
