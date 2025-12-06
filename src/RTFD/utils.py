"""Shared utilities for providers and server."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

import httpx
from loguru import logger
from mcp.types import CallToolResult, TextContent

from .token_counter import count_tokens

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 15.0


def is_fetch_enabled() -> bool:
    """
    Check if documentation content fetching is enabled.

    Controlled by RTFD_FETCH environment variable (default: true).
    Set to 'false', '0', or 'no' to disable.
    """
    fetch_enabled = os.getenv("RTFD_FETCH", "true").lower()
    return fetch_enabled not in ("false", "0", "no")


async def create_http_client() -> httpx.AsyncClient:
    """
    Create a configured HTTP client for provider use.

    Centralizes timeout, user-agent, and redirect configuration.
    """
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )


def serialize_response(data: Any) -> str:
    """
    Convert data to string format.

    Uses JSON with proper escape handling for control characters.
    """
    return json.dumps(data, ensure_ascii=True, default=str)


def serialize_response_with_meta(data: Any) -> CallToolResult:
    """
    Convert data to CallToolResult with optional token statistics in _meta.

    When RTFD_TRACK_TOKENS=true, calculates token stats.
    When false (default), only serializes to JSON.

    Token statistics are included in _meta field, which is NOT sent to the LLM
    and only visible in Claude Code's special logs/metadata (set RTFD_TRACK_TOKENS=true to enable).

    Args:
        data: Python object to serialize (dict, list, etc.)

    Returns:
        CallToolResult with:
          - content: Serialized data in JSON format
          - _meta: Token statistics (only if tracking enabled)
    """
    track_tokens = os.getenv("RTFD_TRACK_TOKENS", "false").lower() == "true"

    response_text = json.dumps(data, ensure_ascii=True, default=str)

    # If token tracking is disabled, just serialize to JSON
    if not track_tokens:
        return CallToolResult(content=[TextContent(type="text", text=response_text)])

    # Token tracking enabled
    try:
        # Calculate token statistics
        token_count = count_tokens(response_text)

        token_stats = {
            "tokens_json": token_count,
            "tokens_sent": token_count,
            "format": "json",
            "bytes_json": len(response_text),
        }

        # Return CallToolResult with content and metadata
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)],
            _meta={"token_stats": token_stats},
        )
    except Exception as e:
        # Fallback: still return response, but with error in metadata
        return CallToolResult(
            content=[TextContent(type="text", text=response_text)],
            _meta={"token_stats": {"error": f"Token counting failed: {e!s}"}},
        )


def get_cache_config() -> tuple[bool, float]:
    """
    Get cache configuration.

    Returns:
        Tuple of (enabled, ttl_seconds)
    """
    enabled = os.getenv("RTFD_CACHE_ENABLED", "true").lower() not in ("false", "0", "no")
    try:
        ttl = float(os.getenv("RTFD_CACHE_TTL", "604800"))  # Default 1 week
    except ValueError:
        ttl = 604800.0
    return enabled, ttl


def get_github_token() -> str | None:
    """
    Get GitHub token based on configured authentication method.

    Authentication method is configured via GITHUB_AUTH environment variable:
    - "token": Only use GITHUB_TOKEN environment variable (default)
    - "cli": Only use gh CLI auth token
    - "auto": Try GITHUB_TOKEN first, then fall back to gh CLI
    - "disabled": Disable GitHub authentication entirely

    Returns:
        GitHub token as string or None if not available or disabled
    """
    auth_method = os.getenv("GITHUB_AUTH", "token").lower()

    # GitHub authentication disabled
    if auth_method == "disabled":
        return None

    # Try token from environment variable
    if auth_method in ("token", "auto"):
        token = os.getenv("GITHUB_TOKEN")
        if token:
            return token
        # If method is just "token" and we didn't find one, don't try other methods
        if auth_method == "token":
            logger.error("GitHub token not found in environment")
            return None

    # Try gh CLI if allowed by auth method
    if auth_method in ("cli", "auto") and shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            # If gh command fails for any reason, continue to return None
            pass

    logger.error("GitHub token not found via configured methods")
    return None
