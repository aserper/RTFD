"""Pytest configuration and fixtures for RTFD tests."""

import os
import pytest


@pytest.fixture(scope="module")
def vcr_config():
    """
    VCR configuration for integration tests.

    This fixture configures how pytest-recording interacts with external APIs:
    - Records responses to cassettes on first run
    - Replays recorded responses on subsequent runs
    - Filters sensitive headers (Authorization, API keys)
    """
    return {
        # Where to store cassette files
        "cassette_library_dir": "tests/cassettes",

        # Filter sensitive information from cassettes
        "filter_headers": [
            "authorization",
            "x-api-key",
            "x-auth-token",
        ],

        # Filter query parameters that might contain secrets
        "filter_query_parameters": [
            "api_key",
            "apikey",
            "token",
        ],

        # Match requests by method, scheme, host, port, path, and query
        "match_on": ["method", "scheme", "host", "port", "path", "query"],

        # Record mode is controlled by --record-mode CLI option
        # Default: 'none' (only use cassettes, fail if missing)
        # Use: pytest --record-mode=once (record if cassette missing)
        # Use: pytest --record-mode=rewrite (re-record all cassettes)
    }


@pytest.fixture(scope="session")
def vcr_cassette_dir(request):
    """Ensure cassette directory exists."""
    cassette_dir = "tests/cassettes"
    os.makedirs(cassette_dir, exist_ok=True)
    return cassette_dir


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests that use real API cassettes",
    )
    config.addinivalue_line(
        "markers",
        "requires_auth: marks tests that require API authentication to record cassettes",
    )


def pytest_recording_configure(config, vcr):
    """
    Hook to configure VCR instance.

    This is called by pytest-recording to allow custom VCR configuration.
    Useful for registering custom matchers, persisters, etc.
    """
    # Custom matcher example (if needed in future)
    # def custom_matcher(r1, r2):
    #     return r1.uri == r2.uri and r1.method == r2.method
    # vcr.register_matcher("custom", custom_matcher)
    pass
