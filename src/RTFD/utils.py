"""Shared utilities for providers and server."""

from __future__ import annotations

from typing import Any

import httpx
import json
import os
from toon import encode

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 15.0


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
    
    Uses TOON by default for token efficiency, but falls back to JSON
    if USE_TOON environment variable is set to 'false'.
    """
    use_toon = os.getenv("USE_TOON", "true").lower() == "true"
    
    if use_toon:
        return encode(data)
    return json.dumps(data)
