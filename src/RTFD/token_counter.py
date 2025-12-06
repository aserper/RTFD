"""Token counting utilities for response size tracking."""

from __future__ import annotations

import tiktoken

# Use cl100k_base encoding (used by GPT-4, Claude, and most modern LLMs)
_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """
    Count tokens in a string using tiktoken's cl100k_base encoding.

    Args:
        text: String to count tokens in

    Returns:
        Number of tokens
    """
    return len(_encoding.encode(text))
