"""Tavily search tool for news and information retrieval."""

from langchain_core.tools import tool
from tavily import TavilyClient

from src.config import get_settings


def _get_tavily_client() -> TavilyClient:
    """Get configured Tavily client."""
    settings = get_settings()
    return TavilyClient(api_key=settings.tavily_api_key)


@tool
def search_news(
    query: str,
    max_results: int = 5,
) -> dict:
    """
    Search for news and articles using Tavily.

    Args:
        query: Search query (e.g., "new energy vehicle news").
        max_results: Maximum number of results to return.

    Returns:
        Search results with titles, URLs, and snippets.
    """
    client = _get_tavily_client()

    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=True,
    )

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
        })

    return {
        "answer": response.get("answer", ""),
        "results": results,
        "query": query,
    }


@tool
def search_general(
    query: str,
    max_results: int = 5,
) -> dict:
    """
    General web search using Tavily.

    Args:
        query: Search query.
        max_results: Maximum number of results to return.

    Returns:
        Search results with titles, URLs, and snippets.
    """
    client = _get_tavily_client()

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
    )

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
        })

    return {
        "results": results,
        "query": query,
    }


# Export all search tools
search_tools = [search_news, search_general]
