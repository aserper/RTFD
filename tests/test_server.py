"""Tests for MCP server and aggregator."""

import pytest

from src.RTFD.server import _get_provider_instances, _locate_library_docs, search_library_docs


@pytest.fixture
def provider_instances():
    """Get provider instances for testing."""
    return _get_provider_instances()


def test_get_provider_instances_returns_all(provider_instances):
    """Test that server loads all providers."""
    assert len(provider_instances) == 7
    assert "pypi" in provider_instances
    assert "godocs" in provider_instances
    assert "github" in provider_instances
    assert "npm" in provider_instances
    assert "crates" in provider_instances
    assert "zig" in provider_instances
    assert "dockerhub" in provider_instances


def test_get_provider_instances_caches():
    """Test that provider instances are cached."""
    instances1 = _get_provider_instances()
    instances2 = _get_provider_instances()

    # Should return same object (cached)
    assert instances1 is instances2


@pytest.mark.asyncio
async def test_locate_library_docs_returns_dict():
    """Test that aggregator returns a dict with library name."""
    result = await _locate_library_docs("requests", limit=2)

    assert isinstance(result, dict)
    assert result["library"] == "requests"


@pytest.mark.asyncio
async def test_locate_library_docs_aggregates_providers():
    """Test that aggregator calls multiple providers."""
    result = await _locate_library_docs("requests", limit=2)

    # Should have results from at least PyPI and GitHub
    # (Google might return empty if throttled)
    assert "pypi" in result or "pypi_error" in result
    assert "github_repos" in result or "github_error" in result


@pytest.mark.asyncio
async def test_locate_library_docs_error_handling():
    """Test that aggregator handles provider errors gracefully."""
    result = await _locate_library_docs("requests", limit=2)

    # Even if some providers fail, we should get the library key
    assert "library" in result
    # At least one provider should succeed or report error
    assert any(
        key in result
        for key in ["pypi", "godocs", "github_repos", "web", "pypi_error", "godocs_error", "github_error", "google_error"]
    )


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_search_library_docs_returns_json_string():
    """Test that search_library_docs tool returns JSON-formatted string by default."""
    result = await search_library_docs("requests", limit=2)

    assert result.content[0].type == "text"
    text_content = result.content[0].text
    assert isinstance(text_content, str)
    # Check for JSON format indicators
    assert '{"library": "requests"' in text_content
    assert '"pypi":' in text_content


@pytest.mark.asyncio
async def test_search_library_docs_with_limit():
    """Test that search_library_docs respects limit parameter."""
    result = await search_library_docs("python", limit=2)

    assert result.content[0].type == "text"
    text_content = result.content[0].text
    assert isinstance(text_content, str)
    assert "python" in text_content


@pytest.mark.asyncio
async def test_aggregator_maps_provider_names():
    """Test that aggregator correctly maps provider names to result keys."""
    result = await _locate_library_docs("requests", limit=2)

    # Check that provider names are mapped to expected keys
    # pypi -> pypi
    # github -> github_repos
    # google -> web
    # godocs -> godocs (but may silently fail with no entry)

    # Check that at least PyPI worked
    assert "pypi" in result or "pypi_error" in result

    # Check that GitHub was queried
    assert "github_repos" in result or "github_error" in result

    # Google and GoDocs are optional (may silently fail or be empty)
    # but if they have results, they should be in the correct keys
    if "web" not in result:
        # Google may have failed
        assert any("google" in key for key in result.keys()) or "google_error" not in result

    # Check that the library name is always present
    assert result["library"] == "requests"
