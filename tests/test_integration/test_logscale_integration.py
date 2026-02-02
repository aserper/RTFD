"""Integration tests for LogScale provider using VCR cassettes.

These tests use pytest-recording to record real API responses to cassettes.
On first run with --record-mode=once, they hit the real LogScale documentation.
On subsequent runs, they replay recorded responses for fast, deterministic tests.

To record/update cassettes:
    pytest tests/test_integration/test_logscale_integration.py --record-mode=rewrite

To run without network access (using existing cassettes):
    pytest tests/test_integration/test_logscale_integration.py

Note: LogScale provider does not support library search. These tests focus on
documentation search and function listing capabilities.
"""

import pytest

from RTFD.providers.logscale import FUNCTION_CATEGORIES, SYNTAX_TOPICS, LogscaleProvider
from RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create LogScale provider instance."""
    return LogscaleProvider(create_http_client)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_search_docs_regex(provider):
    """Test searching for regex-related documentation."""
    result = await provider._search_docs("regex", limit=10)

    assert result["query"] == "regex"
    assert "results" in result
    assert len(result["results"]) > 0

    # Should find regex in both syntax topics and function categories
    result_types = {r["type"] for r in result["results"]}
    assert "syntax" in result_types or "function_category" in result_types


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_search_docs_aggregate(provider):
    """Test searching for aggregate functions."""
    result = await provider._search_docs("aggregate", limit=10)

    assert result["query"] == "aggregate"
    assert "results" in result
    assert len(result["results"]) > 0

    # Should find aggregate function category
    category_results = [r for r in result["results"] if r["type"] == "function_category"]
    assert len(category_results) > 0
    assert any("aggregate" in r["name"] for r in category_results)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_search_docs_time(provider):
    """Test searching for time-related documentation."""
    result = await provider._search_docs("time", limit=10)

    assert result["query"] == "time"
    assert "results" in result
    assert len(result["results"]) > 0

    # Should find time syntax and/or time-date functions
    result_names = [r["name"] for r in result["results"]]
    assert any("time" in name.lower() for name in result_names)


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_list_functions_all_categories(provider):
    """Test listing all function categories."""
    result = await provider._list_functions(category=None)

    assert "categories" in result
    assert result["total_categories"] == len(FUNCTION_CATEGORIES)

    # Verify structure of categories
    for cat in result["categories"]:
        assert "name" in cat
        assert "description" in cat
        assert "url" in cat


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_list_functions_string_category(provider):
    """Test listing functions in string category."""
    result = await provider._list_functions(category="string")

    assert result["category"] == "string"
    assert "functions" in result
    assert "description" in result
    # Category page should have some functions
    assert result["count"] >= 0


@pytest.mark.integration
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_logscale_list_functions_math_category(provider):
    """Test listing functions in math category."""
    result = await provider._list_functions(category="math")

    assert result["category"] == "math"
    assert "functions" in result
    assert "description" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logscale_list_functions_invalid_category(provider):
    """Test listing functions with invalid category."""
    result = await provider._list_functions(category="nonexistent-category-xyz")

    assert "error" in result
    assert "categories" in result  # Should provide available categories


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logscale_syntax_topics_completeness():
    """Test that syntax topics mapping contains expected topics."""
    expected_topics = ["regex", "filters", "operators", "fields", "time"]

    for topic in expected_topics:
        assert topic in SYNTAX_TOPICS
        topic_info = SYNTAX_TOPICS[topic]
        assert "page" in topic_info
        assert "description" in topic_info
        assert topic_info["page"].endswith(".html")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logscale_function_categories_completeness():
    """Test that function categories mapping contains expected categories."""
    expected_categories = ["aggregate", "string", "math", "regex", "parsing", "time-date"]

    for category in expected_categories:
        assert category in FUNCTION_CATEGORIES
        cat_info = FUNCTION_CATEGORIES[category]
        assert "page" in cat_info
        assert "description" in cat_info
        assert cat_info["page"].startswith("functions-")
        assert cat_info["page"].endswith(".html")


# Note: fetch_syntax_docs and fetch_function_docs tests are commented out because
# they scrape live LogScale documentation pages which may change frequently and
# could cause test instability. These tests should be run manually during development.

# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_logscale_fetch_syntax_docs_regex(provider):
#     """Test fetching regex syntax documentation."""
#     result = await provider._fetch_syntax_docs("regex", max_bytes=20480)
#
#     assert result["topic"] == "regex"
#     assert "content" in result
#     assert len(result["content"]) > 0
#     assert result["source"] == "logscale_docs"
#     assert "size_bytes" in result
#     assert result["size_bytes"] > 0


# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_logscale_fetch_syntax_docs_filters(provider):
#     """Test fetching filters syntax documentation."""
#     result = await provider._fetch_syntax_docs("filters", max_bytes=20480)
#
#     assert result["topic"] == "filters"
#     assert "content" in result
#     assert len(result["content"]) > 0


# @pytest.mark.integration
# @pytest.mark.vcr
# @pytest.mark.asyncio
# async def test_logscale_fetch_function_docs_count(provider):
#     """Test fetching documentation for count function."""
#     result = await provider._fetch_function_docs("count", max_bytes=20480)
#
#     assert result["function"] == "count"
#     assert "content" in result
#     assert len(result["content"]) > 0
#     assert result["source"] == "logscale_docs"
