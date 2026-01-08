"""Embedding and reranker client."""

from typing import Callable

import httpx

from src.config import get_settings


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Get embeddings for a list of texts using SiliconFlow bge-m3.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors (1024 dimensions each).
    """
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.siliconflow_base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.siliconflow_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.embedding_model,
                "input": texts,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return [item["embedding"] for item in data["data"]]


async def rerank(
    query: str,
    documents: list[str],
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """
    Rerank documents using SiliconFlow bge-reranker.

    Args:
        query: The query to rank against.
        documents: List of documents to rerank.
        top_k: Number of top results to return.

    Returns:
        List of (index, score) tuples sorted by relevance.
    """
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.siliconflow_base_url}/rerank",
            headers={
                "Authorization": f"Bearer {settings.siliconflow_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.reranker_model,
                "query": query,
                "documents": documents,
                "top_n": top_k,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return [(item["index"], item["relevance_score"]) for item in data["results"]]


def create_embedding_function() -> Callable[[list[str]], list[list[float]]]:
    """
    Create a synchronous embedding function for LangGraph store.

    Returns:
        Embedding function compatible with AsyncPostgresStore.
    """
    import asyncio

    def embed(texts: list[str]) -> list[list[float]]:
        return asyncio.get_event_loop().run_until_complete(get_embeddings(texts))

    return embed
