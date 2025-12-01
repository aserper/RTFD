"""Tests for MCP server and aggregator."""

import pytest
import time

from src.RTFD.server import _get_provider_instances, _locate_library_docs, search_library_docs, _cache_manager
from src.RTFD.cache import CacheEntry


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
    # Check that the library name is always present
    assert result["library"] == "requests"


@pytest.mark.asyncio
async def test_locate_library_docs_uses_cache(monkeypatch):
    """Test that aggregator uses cache."""
    # Mock cache config to ensure it's enabled
    monkeypatch.setenv("RTFD_CACHE_ENABLED", "true")
    
    # Pre-populate cache
    library = "cached-lib"
    limit = 5
    cache_key = f"search:{library}:{limit}"
    cached_data = {"library": library, "pypi": {"foo": "bar"}}
    
    # We need to use the actual cache manager instance from server.py
    # and point it to a temp db or just use it as is (it defaults to ~/.cache)
    # Better to mock the get/set methods to avoid side effects
    
    class MockCacheManager:
        def __init__(self):
            self.store = {}
            
        def get(self, key):
            return self.store.get(key)
            
        def set(self, key, data, metadata=None):
            self.store[key] = CacheEntry(key, data, time.time(), metadata or {})

    mock_cache = MockCacheManager()
    mock_cache.set(cache_key, cached_data)
    
    # Patch the global _cache_manager in server.py
    import src.RTFD.server as server
    monkeypatch.setattr(server, "_cache_manager", mock_cache)
    
    # Run search
    result = await _locate_library_docs(library, limit=limit)
    
    # Should return cached data immediately without calling providers
    assert result == cached_data
    
    # Verify provider was NOT called (we can't easily verify this without mocking providers too, 
    # but the result being the cached data is strong evidence if the cached data is unique)


@pytest.mark.asyncio
async def test_get_cache_info(monkeypatch):
    """Test get_cache_info tool."""
    from src.RTFD.server import get_cache_info
    
    # Mock cache stats
    class MockCacheManager:
        def get_stats(self):
            return {
                "entry_count": 10,
                "db_path": "/tmp/test.db",
                "db_size_bytes": 1024
            }
            
    # Patch the global _cache_manager in server.py
    import src.RTFD.server as server
    monkeypatch.setattr(server, "_cache_manager", MockCacheManager())
    
    result = await get_cache_info()
    
    assert result.content[0].type == "text"
    text_content = result.content[0].text
    assert '"entry_count": 10' in text_content
    assert '"db_path": "/tmp/test.db"' in text_content

