"""
Chunking manager for handling large MCP responses.

Provides token-based chunking with continuation support, allowing agents
to request additional content incrementally.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class ChunkingManager:
    """
    Manages chunking of large responses with continuation token support.

    Stores remaining content in SQLite with short TTL, allowing agents
    to retrieve additional chunks on demand.
    """

    def __init__(self, db_path: str | None = None, ttl: int = 600):
        """
        Initialize the chunking manager.

        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
            ttl: Time-to-live for continuations in seconds (default: 600 = 10 minutes)
        """
        if db_path is None:
            # Default to ~/.cache/rtfd/chunking.db
            cache_dir = Path.home() / ".cache" / "rtfd"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(cache_dir / "chunking.db")

        self.db_path = db_path
        self.ttl = ttl
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS continuations (
                    token TEXT PRIMARY KEY,
                    remaining_content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
                """
            )
            conn.commit()

    def store_continuation(self, remaining_content: str, metadata: dict[str, Any]) -> str:
        """
        Store remaining content for later retrieval.

        Args:
            remaining_content: The content to store for the next chunk
            metadata: Metadata about the chunking (chunk_number, total_tokens, etc.)

        Returns:
            Continuation token (UUID) for retrieving the content
        """
        token = str(uuid.uuid4())

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO continuations (token, remaining_content, metadata, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        token,
                        remaining_content,
                        json.dumps(metadata),
                        time.time(),
                    ),
                )
                conn.commit()
        except Exception as e:
            import sys

            sys.stderr.write(f"Chunking storage error: {e}\n")
            raise

        return token

    def get_next_chunk(self, token: str, chunk_size: int) -> dict[str, Any] | None:
        """
        Retrieve the next chunk of content using a continuation token.

        Args:
            token: Continuation token from previous chunk
            chunk_size: Maximum tokens for this chunk

        Returns:
            Dict with chunk data or None if token not found/expired
        """
        try:
            # Clean up expired entries first
            self.cleanup_expired()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT remaining_content, metadata, timestamp FROM continuations WHERE token = ?",
                    (token,),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                remaining_content, metadata_json, timestamp = row
                metadata = json.loads(metadata_json)

                # Check if expired
                if time.time() - timestamp > self.ttl:
                    # Clean up expired entry
                    conn.execute("DELETE FROM continuations WHERE token = ?", (token,))
                    conn.commit()
                    return None

                # Calculate chunk boundaries based on tokens
                from .token_counter import _encoding

                tokens = _encoding.encode(remaining_content)

                if len(tokens) <= chunk_size:
                    # This is the last chunk
                    chunk_content = remaining_content
                    has_more = False
                    new_token = None
                    remaining_tokens = 0

                    # Delete the continuation
                    conn.execute("DELETE FROM continuations WHERE token = ?", (token,))
                    conn.commit()
                else:
                    # Need to split into another chunk
                    chunk_tokens = tokens[:chunk_size]
                    remaining_tokens_list = tokens[chunk_size:]

                    chunk_content = _encoding.decode(chunk_tokens)
                    new_remaining = _encoding.decode(remaining_tokens_list)

                    has_more = True
                    remaining_tokens = len(remaining_tokens_list)

                    # Update metadata for next chunk
                    new_metadata = metadata.copy()
                    new_metadata["chunk_number"] = metadata.get("chunk_number", 1) + 1

                    # Store new continuation
                    new_token = self.store_continuation(new_remaining, new_metadata)

                    # Delete old token
                    conn.execute("DELETE FROM continuations WHERE token = ?", (token,))
                    conn.commit()

                return {
                    "content": chunk_content,
                    "chunk_number": metadata.get("chunk_number", 1) + 1,
                    "has_more": has_more,
                    "continuation_token": new_token,
                    "tokens_in_chunk": len(_encoding.encode(chunk_content)),
                    "remaining_tokens": remaining_tokens,
                }

        except Exception as e:
            import sys

            sys.stderr.write(f"Chunking retrieval error: {e}\n")
            return None

    def cleanup_expired(self) -> int:
        """
        Remove expired continuations.

        Returns:
            Number of entries removed
        """
        cutoff = time.time() - self.ttl
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM continuations WHERE timestamp < ?", (cutoff,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            import sys

            sys.stderr.write(f"Chunking cleanup error: {e}\n")
            return 0


def get_chunk_size() -> int:
    """
    Get the chunk size from environment or use default.

    Returns:
        Chunk size in tokens (0 means chunking disabled)
    """
    try:
        return int(os.getenv("RTFD_CHUNK_TOKENS", "2000"))
    except ValueError:
        return 2000
