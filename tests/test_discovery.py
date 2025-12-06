"""Tests for provider auto-discovery mechanism."""

from src.RTFD.providers import discover_providers, get_provider_metadata_all
from src.RTFD.providers.base import BaseProvider, ProviderMetadata


def test_discover_providers_finds_all():
    """Test that discovery finds all providers."""
    providers = discover_providers()

    assert len(providers) == 8
    assert "pypi" in providers
    assert "godocs" in providers
    assert "github" in providers
    assert "npm" in providers
    assert "crates" in providers
    assert "zig" in providers
    assert "dockerhub" in providers
    assert "gcp" in providers


def test_all_providers_are_base_provider_subclasses():
    """Test that all discovered providers are BaseProvider subclasses."""
    providers = discover_providers()

    for _name, provider_class in providers.items():
        assert issubclass(provider_class, BaseProvider)
        assert provider_class is not BaseProvider


def test_provider_metadata():
    """Test that all providers have valid metadata."""
    providers = discover_providers()

    for name, provider_class in providers.items():
        instance = provider_class(lambda: None)
        metadata = instance.get_metadata()

        assert isinstance(metadata, ProviderMetadata)
        assert metadata.name == name
        assert isinstance(metadata.description, str)
        assert isinstance(metadata.expose_as_tool, bool)
        assert isinstance(metadata.tool_names, list)
        assert isinstance(metadata.supports_library_search, bool)


def test_get_provider_metadata_all():
    """Test get_provider_metadata_all returns metadata for all providers."""
    metadata_list = get_provider_metadata_all()

    assert len(metadata_list) == 8

    metadata_names = {m.name for m in metadata_list}
    assert metadata_names == {
        "pypi",
        "godocs",
        "github",
        "npm",
        "crates",
        "zig",
        "dockerhub",
        "gcp",
    }


def test_discovery_caches_results():
    """Test that discovery caches results and doesn't re-import."""
    providers1 = discover_providers()
    providers2 = discover_providers()

    # Should return the same dict object (cached)
    assert providers1 is providers2


def test_provider_tools_metadata():
    """Test that providers with expose_as_tool=True have tool_names."""
    providers = discover_providers()

    for _name, provider_class in providers.items():
        instance = provider_class(lambda: None)
        metadata = instance.get_metadata()

        if metadata.expose_as_tool:
            assert len(metadata.tool_names) > 0
            for tool_name in metadata.tool_names:
                assert isinstance(tool_name, str)
                assert len(tool_name) > 0
