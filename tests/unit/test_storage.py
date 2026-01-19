"""Unit tests for storage."""

import pytest
from src.core.storage import MemoryStorage


@pytest.mark.asyncio
async def test_memory_storage_set_get():
    """Test basic set and get operations."""
    storage = MemoryStorage()
    
    await storage.set("key1", "value1")
    value = await storage.get("key1")
    
    assert value == "value1"


@pytest.mark.asyncio
async def test_memory_storage_delete():
    """Test delete operation."""
    storage = MemoryStorage()
    
    await storage.set("key1", "value1")
    deleted = await storage.delete("key1")
    value = await storage.get("key1")
    
    assert deleted == True
    assert value is None


@pytest.mark.asyncio
async def test_memory_storage_exists():
    """Test exists operation."""
    storage = MemoryStorage()
    
    await storage.set("key1", "value1")
    
    assert await storage.exists("key1") == True
    assert await storage.exists("key2") == False


@pytest.mark.asyncio
async def test_memory_storage_keys():
    """Test keys operation."""
    storage = MemoryStorage()
    
    await storage.set("test:1", "value1")
    await storage.set("test:2", "value2")
    await storage.set("other:1", "value3")
    
    all_keys = await storage.keys("*")
    test_keys = await storage.keys("test:*")
    
    assert len(all_keys) == 3
    assert len(test_keys) == 2


@pytest.mark.asyncio
async def test_memory_storage_clear():
    """Test clear operation."""
    storage = MemoryStorage()
    
    await storage.set("key1", "value1")
    await storage.set("key2", "value2")
    await storage.clear()
    
    assert await storage.exists("key1") == False
    assert await storage.exists("key2") == False


@pytest.mark.asyncio
async def test_memory_storage_ttl():
    """Test TTL functionality."""
    import asyncio
    storage = MemoryStorage()
    
    # Set with 1 second TTL
    await storage.set("key1", "value1", ttl=1)
    
    # Should exist immediately
    assert await storage.get("key1") == "value1"
    
    # Wait for expiry
    await asyncio.sleep(1.1)
    
    # Should be expired
    assert await storage.get("key1") is None

