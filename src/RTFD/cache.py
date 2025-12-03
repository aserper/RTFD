"""
Cache manager using SQLite for storing library search results.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import sys


@dataclass
class CacheEntry:
    """Represents a cached item."""
    key: str
    data: Any
    timestamp: float
    metadata: Dict[str, Any]


class CacheManager:
    """
    Manages a SQLite-based cache for search results.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the cache manager.

        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to ~/.cache/rtfd/cache.db
            cache_dir = Path.home() / ".cache" / "rtfd"
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(cache_dir / "cache.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT
                )
                """
            )
            conn.commit()

    def get(self, key: str) -> Optional[CacheEntry]:
        """
        Retrieve an item from the cache.

        Args:
            key: Unique cache key.

        Returns:
            CacheEntry if found, None otherwise.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data, timestamp, metadata FROM cache WHERE key = ?", (key,)
                )
                row = cursor.fetchone()

                if row:
                    data_json, timestamp, metadata_json = row
                    return CacheEntry(
                        key=key,
                        data=json.loads(data_json),
                        timestamp=timestamp,
                        metadata=json.loads(metadata_json) if metadata_json else {},
                    )
        except Exception as e:
            sys.stderr.write(f"Cache read error: {e}\n")
        
        return None

    def set(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Store an item in the cache.

        Args:
            key: Unique cache key.
            data: Data to store (must be JSON serializable).
            metadata: Optional metadata for conditional requests.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache (key, data, timestamp, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        key,
                        json.dumps(data),
                        time.time(),
                        json.dumps(metadata) if metadata else None,
                    ),
                )
                conn.commit()
        except Exception as e:
            sys.stderr.write(f"Cache write error: {e}\n")

    def invalidate(self, key: str) -> None:
        """
        Remove an item from the cache.

        Args:
            key: Unique cache key.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
        except Exception as e:
            sys.stderr.write(f"Cache invalidate error: {e}\n")

    def cleanup(self, ttl: float) -> int:
        """
        Remove expired entries.

        Args:
            ttl: Time-to-live in seconds.

        Returns:
            Number of entries removed.
        """
        cutoff = time.time() - ttl
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE timestamp < ?", (cutoff,)
                )
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            sys.stderr.write(f"Cache cleanup error: {e}\n")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict containing entry_count, db_path, and db_size_bytes.
        """
        stats = {
            "entry_count": 0,
            "db_path": self.db_path,
            "db_size_bytes": 0,
        }

        try:
            if os.path.exists(self.db_path):
                stats["db_size_bytes"] = os.path.getsize(self.db_path)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache")
                stats["entry_count"] = cursor.fetchone()[0]
        except Exception as e:
            sys.stderr.write(f"Cache stats error: {e}\n")

        return stats

    def get_all_entries(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information about all cached entries.

        Returns:
            Dict mapping cache keys to entry details (age, size, content preview).
        """
        entries = {}
        current_time = time.time()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT key, data, timestamp FROM cache ORDER BY timestamp DESC"
                )
                rows = cursor.fetchall()

                for key, data_json, timestamp in rows:
                    age_seconds = current_time - timestamp
                    data = json.loads(data_json)
                    data_size = len(data_json.encode("utf-8"))

                    entries[key] = {
                        "age_seconds": round(age_seconds, 2),
                        "size_bytes": data_size,
                        "timestamp": timestamp,
                        "content_preview": self._get_preview(data),
                    }
        except Exception as e:
            sys.stderr.write(f"Cache get_all_entries error: {e}\n")

        return entries

    @staticmethod
    def _get_preview(data: Any, max_length: int = 150) -> str:
        """
        Get a preview of cached data.

        Args:
            data: The data to preview.
            max_length: Maximum length of preview string.

        Returns:
            String preview of the data.
        """
        if isinstance(data, dict):
            if "library" in data:
                library = data.get("library", "")
                
                # Try to find a description in provider results
                description = ""
                
                # Check PyPI
                if "pypi" in data and isinstance(data["pypi"], dict):
                    description = data["pypi"].get("summary") or data["pypi"].get("description") or ""
                
                # Check NPM
                if not description and "npm" in data and isinstance(data["npm"], dict):
                    description = data["npm"].get("summary") or data["npm"].get("description") or ""
                    
                # Check Crates
                if not description and "crates" in data and isinstance(data["crates"], dict):
                     description = data["crates"].get("description") or ""

                # Check GoDocs
                if not description and "godocs" in data and isinstance(data["godocs"], dict):
                    description = data["godocs"].get("synopsis") or ""

                # Check GitHub
                if not description and "github_repos" in data and isinstance(data["github_repos"], list):
                    if len(data["github_repos"]) > 0:
                         description = data["github_repos"][0].get("description") or ""
                
                if description:
                    if len(description) > 100:
                        description = description[:100] + "..."
                    return f"search:{library} -> {description}"

                keys = [k for k in data.keys() if k != "library"]
                return f"search:{library} -> {', '.join(keys[:3])}"
            # For other dicts, show keys
            keys = list(data.keys())[:3]
            return f"dict: {', '.join(keys)}"
        elif isinstance(data, str):
            return data[:max_length]
        else:
            preview = str(data)[:max_length]
            return preview
