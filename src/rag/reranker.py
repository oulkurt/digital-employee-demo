"""Reranker for improving retrieval quality."""

from dataclasses import dataclass

from src.llm.embedding import rerank


@dataclass
class RankedDocument:
    """A document with its reranking score."""

    content: str
    score: float
    original_index: int


async def rerank_documents(
    query: str,
    documents: list[str],
    top_k: int = 5,
) -> list[RankedDocument]:
    """
    Rerank documents by relevance to a query.

    Args:
        query: The query to rank against.
        documents: List of document contents.
        top_k: Number of top results to return.

    Returns:
        List of RankedDocument sorted by relevance score (descending).
    """
    if not documents:
        return []

    # Get reranking scores from SiliconFlow
    ranked_indices = await rerank(query, documents, top_k=min(top_k, len(documents)))

    results = []
    for idx, score in ranked_indices:
        results.append(
            RankedDocument(
                content=documents[idx],
                score=score,
                original_index=idx,
            )
        )

    return results


async def rerank_memory_results(
    query: str,
    memory_items: list[dict],
    content_key: str = "content",
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank memory items by relevance to a query.

    Args:
        query: The query to rank against.
        memory_items: List of memory dictionaries.
        content_key: Key in the dict that contains the text content.
        top_k: Number of top results to return.

    Returns:
        Reranked list of memory items with added 'rerank_score' field.
    """
    if not memory_items:
        return []

    # Extract content for reranking
    contents = [item.get(content_key, "") for item in memory_items]

    # Get rankings
    ranked = await rerank_documents(query, contents, top_k=top_k)

    # Map back to original items
    results = []
    for r in ranked:
        item = memory_items[r.original_index].copy()
        item["rerank_score"] = r.score
        results.append(item)

    return results
