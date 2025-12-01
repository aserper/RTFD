"""Tests for CacheManager."""

import os
import time
import pytest
from src.RTFD.cache import CacheManager

@pytest.fixture
def cache_db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test_cache.db")

@pytest.fixture
def cache_manager(cache_db_path):
    """Create a CacheManager instance."""
    return CacheManager(db_path=cache_db_path)

def test_cache_set_get(cache_manager):
    """Test setting and getting a value."""
    key = "test_key"
    data = {"foo": "bar"}
    cache_manager.set(key, data)
    
    entry = cache_manager.get(key)
    assert entry is not None
    assert entry.key == key
    assert entry.data == data
    assert entry.metadata == {}

def test_cache_get_missing(cache_manager):
    """Test getting a missing value."""
    entry = cache_manager.get("missing_key")
    assert entry is None

def test_cache_invalidate(cache_manager):
    """Test invalidating a value."""
    key = "test_key"
    data = {"foo": "bar"}
    cache_manager.set(key, data)
    
    cache_manager.invalidate(key)
    entry = cache_manager.get(key)
    assert entry is None

def test_cache_cleanup(cache_manager):
    """Test cleaning up expired values."""
    # Set an entry with a timestamp in the past
    key = "expired_key"
    data = {"foo": "bar"}
    
    # We need to manually insert to control the timestamp
    import sqlite3
    import json
    
    with sqlite3.connect(cache_manager.db_path) as conn:
        conn.execute(
            "INSERT INTO cache (key, data, timestamp, metadata) VALUES (?, ?, ?, ?)",
            (key, json.dumps(data), time.time() - 100, None)
        )
        conn.commit()
        
    # Cleanup with TTL=10 (so the entry is expired)
    removed = cache_manager.cleanup(ttl=10)
    assert removed == 1
    
    entry = cache_manager.get(key)
    assert entry is None

def test_cache_metadata(cache_manager):
    """Test storing and retrieving metadata."""
    key = "meta_key"
    data = {"foo": "bar"}
    metadata = {"etag": "123"}
    
    cache_manager.set(key, data, metadata=metadata)
    
    entry = cache_manager.get(key)
    assert entry is not None
    assert entry.metadata == metadata

def test_cache_stats(cache_manager):
    """Test retrieving cache statistics."""
    # Empty cache
    stats = cache_manager.get_stats()
    assert stats["entry_count"] == 0
    assert stats["db_path"] == cache_manager.db_path
    assert stats["db_size_bytes"] > 0  # DB file exists and has schema
    
    # Add entry
    cache_manager.set("key1", {"foo": "bar"})
    stats = cache_manager.get_stats()
    assert stats["entry_count"] == 1

