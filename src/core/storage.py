"""Abstract storage layer with multiple backend support."""

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

import aiosqlite

from .logger import get_logger

logger = get_logger(__name__)


class Storage(ABC):
    """Abstract storage interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value with optional TTL (seconds)."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all data."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close storage connection."""
        pass


class MemoryStorage(Storage):
    """In-memory storage implementation."""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._ttl: Dict[str, datetime] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        # Check TTL
        if key in self._ttl:
            if datetime.now() > self._ttl[key]:
                await self.delete(key)
                return None
        return self._data.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value with optional TTL."""
        self._data[key] = value
        if ttl:
            from datetime import timedelta
            self._ttl[key] = datetime.now() + timedelta(seconds=ttl)

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if key in self._data:
            del self._data[key]
            self._ttl.pop(key, None)
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    async def clear(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._ttl.clear()

    async def close(self) -> None:
        """Close storage."""
        pass


class SQLiteStorage(Storage):
    """SQLite storage implementation."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def _init_db(self) -> None:
        """Initialize database connection and schema."""
        if self._db is not None:
            return

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at ON kv_store(expires_at)
        """)
        await self._db.commit()
        logger.info("SQLite storage initialized", db_path=self.db_path)

    async def _ensure_connection(self) -> aiosqlite.Connection:
        """Ensure database connection is established."""
        if self._db is None:
            await self._init_db()
        return self._db  # type: ignore

    async def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        db = await self._ensure_connection()
        now = datetime.now().timestamp()
        await db.execute(
            "DELETE FROM kv_store WHERE expires_at IS NOT NULL AND expires_at < ?",
            (now,)
        )
        await db.commit()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        async with self._lock:
            db = await self._ensure_connection()
            await self._cleanup_expired()
            
            cursor = await db.execute(
                "SELECT value FROM kv_store WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value with optional TTL."""
        async with self._lock:
            db = await self._ensure_connection()
            
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = str(value)
            
            # Calculate expiry
            expires_at = None
            if ttl:
                from datetime import timedelta
                expires_at = (datetime.now() + timedelta(seconds=ttl)).timestamp()
            
            await db.execute(
                "INSERT OR REPLACE INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
                (key, serialized, expires_at)
            )
            await db.commit()

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        async with self._lock:
            db = await self._ensure_connection()
            cursor = await db.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            await db.commit()
            return cursor.rowcount > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        async with self._lock:
            db = await self._ensure_connection()
            await self._cleanup_expired()
            
            cursor = await db.execute(
                "SELECT 1 FROM kv_store WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get all keys matching pattern."""
        async with self._lock:
            db = await self._ensure_connection()
            await self._cleanup_expired()
            
            if pattern == "*":
                cursor = await db.execute("SELECT key FROM kv_store")
            else:
                # Convert glob pattern to SQL LIKE pattern
                sql_pattern = pattern.replace("*", "%").replace("?", "_")
                cursor = await db.execute(
                    "SELECT key FROM kv_store WHERE key LIKE ?",
                    (sql_pattern,)
                )
            
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def clear(self) -> None:
        """Clear all data."""
        async with self._lock:
            db = await self._ensure_connection()
            await db.execute("DELETE FROM kv_store")
            await db.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("SQLite storage closed")


# Global storage instance
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = MemoryStorage()
    return _storage


def set_storage(storage: Storage) -> None:
    """Set the global storage instance."""
    global _storage
    _storage = storage


async def init_storage(db_path: Optional[str] = None) -> Storage:
    """Initialize storage backend."""
    if db_path:
        storage = SQLiteStorage(db_path)
        await storage._init_db()
    else:
        storage = MemoryStorage()
    
    set_storage(storage)
    logger.info("Storage initialized", backend=type(storage).__name__)
    return storage

