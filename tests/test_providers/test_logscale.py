"""Tests for LogScale provider."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.RTFD.providers.logscale import (
    FUNCTION_CATEGORIES,
    SYNTAX_TOPICS,
    LogscaleProvider,
)
from src.RTFD.utils import create_http_client


@pytest.fixture
def provider():
    """Create a LogScale provider instance."""
    return LogscaleProvider(create_http_client)


@pytest.fixture
def mock_html_content():
    """Return mock HTML content for LogScale documentation."""
    return """
    <html>
        <body>
            <h1>regex()</h1>
            <p>The regex() function provides a method for executing regular expressions.</p>

            <h2>Parameters</h2>
            <table>
                <tr><th>Name</th><th>Type</th><th>Description</th></tr>
                <tr><td>regex</td><td>string</td><td>The regular expression pattern</td></tr>
                <tr><td>field</td><td>string</td><td>The field to match against</td></tr>
            </table>

            <h2>Examples</h2>
            <pre><code>regex("error.*timeout")</code></pre>
            <p>Matches events containing "error" followed by "timeout".</p>

            <h2>Related Functions</h2>
            <ul>
                <li><a href="functions-replace.html">replace()</a></li>
                <li><a href="functions-split.html">split()</a></li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def mock_functions_page():
    """Return mock HTML for functions listing page."""
    return """
    <html>
        <body>
            <h1>Query Functions</h1>
            <ul>
                <li><a href="functions-regex.html">regex()</a></li>
                <li><a href="functions-split.html">split()</a></li>
                <li><a href="functions-replace.html">replace()</a></li>
                <li><a href="functions-count.html">count()</a></li>
            </ul>
        </body>
    </html>
    """


def test_logscale_metadata(provider):
    """Test LogScale provider metadata."""
    metadata = provider.get_metadata()
    assert metadata.name == "logscale"
    assert metadata.supports_library_search is False
    assert "search_logscale_docs" in metadata.tool_names
    assert "list_logscale_functions" in metadata.tool_names


def test_logscale_metadata_with_fetch(provider):
    """Test LogScale provider includes fetch tools when enabled."""
    metadata = provider.get_metadata()
    # RTFD_FETCH is enabled by default
    assert "logscale_syntax" in metadata.tool_names
    assert "logscale_function" in metadata.tool_names


@pytest.mark.asyncio
async def test_logscale_search_library_not_supported(provider):
    """Test that search_library returns failure as it's not supported."""
    result = await provider.search_library("anything")
    assert result.success is False
    assert "not support" in result.error


@pytest.mark.asyncio
async def test_search_docs_syntax_topics(provider):
    """Test searching for syntax topics."""
    # Search should find regex in syntax topics
    result = await provider._search_docs("regex", limit=10)

    assert result["query"] == "regex"
    assert "results" in result
    assert len(result["results"]) > 0

    # Should find regex syntax topic
    syntax_results = [r for r in result["results"] if r["type"] == "syntax"]
    assert len(syntax_results) > 0


@pytest.mark.asyncio
async def test_search_docs_function_categories(provider):
    """Test searching for function categories."""
    result = await provider._search_docs("aggregate", limit=10)

    assert result["query"] == "aggregate"
    category_results = [r for r in result["results"] if r["type"] == "function_category"]
    assert len(category_results) > 0
    assert any("aggregate" in r["name"] for r in category_results)


@pytest.mark.asyncio
async def test_search_docs_with_functions_page(provider, mock_functions_page):
    """Test searching docs includes function names from page."""
    mock_response = MagicMock()
    mock_response.text = mock_functions_page
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._search_docs("regex", limit=10)

    # Should find regex function from the page
    function_results = [r for r in result["results"] if r["type"] == "function"]
    assert len(function_results) > 0


@pytest.mark.asyncio
async def test_list_functions_all_categories(provider):
    """Test listing all function categories."""
    result = await provider._list_functions(category=None)

    assert "categories" in result
    assert result["total_categories"] == len(FUNCTION_CATEGORIES)

    # Verify some known categories are present
    category_names = [c["name"] for c in result["categories"]]
    assert "aggregate" in category_names
    assert "string" in category_names
    assert "math" in category_names


@pytest.mark.asyncio
async def test_list_functions_by_category(provider, mock_html_content):
    """Test listing functions in a specific category."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._list_functions(category="regex")

    assert result["category"] == "regex"
    assert "functions" in result


@pytest.mark.asyncio
async def test_list_functions_invalid_category(provider):
    """Test listing functions with invalid category."""
    result = await provider._list_functions(category="nonexistent")

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert "categories" in result  # Should provide available categories


@pytest.mark.asyncio
async def test_fetch_syntax_docs_success(provider, mock_html_content):
    """Test fetching syntax documentation."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._fetch_syntax_docs("regex", max_bytes=20480)

    assert result["topic"] == "regex"
    assert "content" in result
    assert result["size_bytes"] > 0
    assert "error" not in result


@pytest.mark.asyncio
async def test_fetch_syntax_docs_invalid_topic(provider):
    """Test fetching syntax docs for invalid topic."""
    result = await provider._fetch_syntax_docs("nonexistent_topic")

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_fetch_function_docs_success(provider, mock_html_content):
    """Test fetching function documentation."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._fetch_function_docs("regex", max_bytes=20480)

    assert result["function"] == "regex"
    assert "content" in result
    assert result["size_bytes"] > 0
    assert "Parameters" in result["content"]


@pytest.mark.asyncio
async def test_fetch_function_docs_namespaced(provider, mock_html_content):
    """Test fetching docs for namespaced function like array:append."""
    mock_response = MagicMock()
    mock_response.text = mock_html_content
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)

    # Should normalize array:append to array-append for URL
    result = await provider._fetch_function_docs("array:append", max_bytes=20480)

    # Verify the URL was constructed correctly (via the mock call)
    call_args = mock_client.get.call_args
    url = call_args[0][0]
    assert "functions-array-append.html" in url


@pytest.mark.asyncio
async def test_fetch_function_docs_404_with_suggestions(provider, mock_functions_page):
    """Test fetching docs for nonexistent function provides suggestions."""
    # First call returns 404, second call (search) returns function list
    mock_404_response = MagicMock()
    mock_404_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock(status_code=404)
    )

    mock_search_response = MagicMock()
    mock_search_response.text = mock_functions_page
    mock_search_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_404_response, mock_search_response]
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._fetch_function_docs("regx", max_bytes=20480)

    assert "error" in result
    # Should provide suggestions if similar functions found
    if "suggestions" in result:
        assert len(result["suggestions"]) > 0


@pytest.mark.asyncio
async def test_fetch_function_http_error(provider):
    """Test handling of HTTP errors when fetching function docs."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock(status_code=500)
    )

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    result = await provider._fetch_function_docs("regex", max_bytes=20480)

    assert "error" in result
    assert "500" in result["error"]


def test_get_tools(provider):
    """Test get_tools returns expected tools."""
    tools = provider.get_tools()

    assert "search_logscale_docs" in tools
    assert "list_logscale_functions" in tools
    assert "logscale_syntax" in tools
    assert "logscale_function" in tools

    # Verify all are callable
    for name, func in tools.items():
        assert callable(func), f"Tool {name} is not callable"


@pytest.mark.asyncio
async def test_search_tool_returns_call_tool_result(provider, mock_functions_page):
    """Test that search tool returns proper CallToolResult."""
    mock_response = MagicMock()
    mock_response.text = mock_functions_page
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    async def mock_factory():
        return mock_client

    provider = LogscaleProvider(mock_factory)
    tools = provider.get_tools()

    result = await tools["search_logscale_docs"]("regex", limit=5)

    assert result.content[0].type == "text"
    assert "regex" in result.content[0].text.lower()


def test_syntax_topics_mapping():
    """Test that syntax topics mapping is properly defined."""
    assert len(SYNTAX_TOPICS) > 0

    for key, info in SYNTAX_TOPICS.items():
        assert "page" in info
        assert "description" in info
        assert info["page"].endswith(".html")


def test_function_categories_mapping():
    """Test that function categories mapping is properly defined."""
    assert len(FUNCTION_CATEGORIES) > 0

    for key, info in FUNCTION_CATEGORIES.items():
        assert "page" in info
        assert "description" in info
        assert info["page"].startswith("functions-")
        assert info["page"].endswith(".html")
