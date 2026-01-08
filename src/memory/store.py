"""PostgreSQL store configuration for LangGraph with LangMem."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from langgraph.store.postgres import AsyncPostgresStore  # from langgraph-checkpoint-postgres

from src.config import get_settings
from src.llm.embedding import get_embeddings


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Async embedding function for store index."""
    return await get_embeddings(texts)


@asynccontextmanager
async def get_store() -> AsyncGenerator[AsyncPostgresStore, None]:
    """
    Create and yield an AsyncPostgresStore instance.

    The store is configured with:
    - PostgreSQL connection from DATABASE_URL
    - Vector index using bge-m3 embeddings (1024 dims)

    Usage:
        async with get_store() as store:
            # use store
    """
    settings = get_settings()

    async with AsyncPostgresStore.from_conn_string(
        conn_string=settings.database_url,
        index={
            "dims": 1024,
            "embed": _embed_texts,
        },
    ) as store:
        yield store


async def init_store() -> None:
    """
    Initialize the database schema for the store.

    Run this once to set up the required tables.
    """
    async with get_store() as store:
        await store.setup()


if __name__ == "__main__":
    import asyncio
    import sys

    if "--init" in sys.argv:
        print("Initializing database schema...")
        asyncio.run(init_store())
        print("Done.")
