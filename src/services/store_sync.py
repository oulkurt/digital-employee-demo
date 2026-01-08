"""Synchronous wrapper for AsyncPostgresStore."""

import asyncio
import atexit
from typing import Any

from langgraph.store.postgres import AsyncPostgresStore

from src.config import get_settings
from src.llm.embedding import get_embeddings

# Global store instance
_store: AsyncPostgresStore | None = None
_store_cm = None  # Context manager reference
_loop: asyncio.AbstractEventLoop | None = None


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Async embedding function for store index."""
    return await get_embeddings(texts)


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Get or create an event loop for sync operations."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def connect_store() -> AsyncPostgresStore:
    """
    Connect to the store synchronously.

    Returns the connected store instance. Safe to call multiple times;
    returns the same instance if already connected.
    """
    global _store, _store_cm

    if _store is not None:
        return _store

    settings = get_settings()
    loop = _get_or_create_loop()

    async def _connect():
        store_cm = AsyncPostgresStore.from_conn_string(
            conn_string=settings.database_url,
            index={
                "dims": 1024,
                "embed": _embed_texts,
            },
        )
        # Enter the async context manager to get the actual store
        store = await store_cm.__aenter__()
        return store, store_cm

    _store, _store_cm = loop.run_until_complete(_connect())

    # Register cleanup on exit
    atexit.register(close_store)

    return _store


def close_store() -> None:
    """Close the store connection."""
    global _store, _store_cm, _loop

    if _store_cm is not None and _loop is not None:
        try:
            _loop.run_until_complete(_store_cm.__aexit__(None, None, None))
        except Exception:
            pass
        _store = None
        _store_cm = None


def get_connected_store() -> AsyncPostgresStore | None:
    """Get the currently connected store, or None if not connected."""
    return _store


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get the global event loop used by store operations."""
    return _get_or_create_loop()


def run_async(coro) -> Any:
    """Run an async coroutine synchronously."""
    loop = _get_or_create_loop()
    return loop.run_until_complete(coro)
