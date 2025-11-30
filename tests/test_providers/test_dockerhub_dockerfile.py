import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp.types import CallToolResult
from RTFD.providers.dockerhub import DockerHubProvider

@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    return client

@pytest.fixture
def provider(mock_http_client):
    # The factory must be an async function or return an awaitable
    factory = AsyncMock(return_value=mock_http_client)
    return DockerHubProvider(factory)

@pytest.mark.asyncio
async def test_fetch_dockerfile_success(provider, mock_http_client):
    # Mock DockerHub metadata response with a GitHub link in full_description
    metadata_response = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "name": "python",
            "full_description": "Some text\n- [Dockerfile](https://github.com/docker-library/python/blob/master/3.11/slim/Dockerfile)\nMore text"
        }),
        raise_for_status=MagicMock()
    )
    
    mock_http_client.get.side_effect = [
        # 1. _fetch_image_metadata call
        metadata_response,
        # 2. _fetch_dockerfile re-fetch call
        metadata_response,
        # 3. GitHub raw content call
        MagicMock(
            status_code=200,
            text="FROM debian:bookworm-slim\nRUN apt-get update",
            raise_for_status=MagicMock()
        )
    ]

    result = await provider._fetch_dockerfile("python")

    assert result["image"] == "python"
    assert result["content"] == "FROM debian:bookworm-slim\nRUN apt-get update"
    assert result["source"] == "https://raw.githubusercontent.com/docker-library/python/master/3.11/slim/Dockerfile"
    assert result["found_in_description"] is True

    # Verify calls
    assert mock_http_client.get.call_count == 3

@pytest.mark.asyncio
async def test_fetch_dockerfile_no_link(provider, mock_http_client):
    # Mock DockerHub metadata response WITHOUT a GitHub link
    response = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "name": "python",
            "full_description": "Just some description without links."
        }),
        raise_for_status=MagicMock()
    )
    mock_http_client.get.side_effect = [response, response]

    result = await provider._fetch_dockerfile("python")

    assert result["image"] == "python"
    assert "error" in result
    assert "No GitHub Dockerfile link found" in result["error"]
    assert result["source"] == "dockerhub_description"

@pytest.mark.asyncio
async def test_fetch_dockerfile_api_error(provider, mock_http_client):
    # Mock DockerHub API failure
    mock_http_client.get.side_effect = Exception("API Error")

    result = await provider._fetch_dockerfile("python")

    assert result["image"] == "python"
    assert "error" in result
    # The error comes from _fetch_image_metadata catching the exception
    assert "Failed to fetch metadata" in result["error"]

@pytest.mark.asyncio
async def test_tool_registration(provider):
    tools = provider.get_tools()
    assert "fetch_dockerfile" in tools
    assert callable(tools["fetch_dockerfile"])
