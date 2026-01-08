"""LangGraph ReAct Agent with LangMem memory integration."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.store.base import BaseStore

from src.agent.prompts import build_system_prompt
from src.llm.chat import get_chat_model
from src.rag.reranker import rerank_memory_results
from src.tools.calendar import calendar_tools
from src.tools.search import search_tools


async def retrieve_user_memories(
    store: BaseStore,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve and rerank user memories relevant to the query.

    Args:
        store: The memory store.
        user_id: User identifier.
        query: Query to search memories for.
        top_k: Maximum number of memories to return.

    Returns:
        List of relevant memory items.
    """
    namespace = ("user_memories", user_id)

    # Search memories using vector similarity
    results = await store.asearch(
        namespace,  # positional argument
        query=query,
        limit=top_k * 2,  # Get more for reranking
    )

    if not results:
        return []

    # Extract memory values
    memories = [item.value for item in results]

    # Rerank for better relevance
    reranked = await rerank_memory_results(
        query=query,
        memory_items=memories,
        content_key="content",
        top_k=top_k,
    )

    return reranked


def create_agent(store: BaseStore | None = None):
    """
    Create a ReAct agent with all tools configured.

    Args:
        store: Optional memory store for LangMem integration.

    Returns:
        Configured LangGraph agent.
    """
    model = get_chat_model()

    # Combine all tools
    tools = [
        *calendar_tools,
        *search_tools,
    ]

    # Create the agent
    agent = create_react_agent(
        model=model,
        tools=tools,
        store=store,
    )

    return agent


async def run_agent(
    agent,
    message: str,
    store: BaseStore | None = None,
    user_id: str = "demo_user",
    thread_id: str = "default",
) -> dict[str, Any]:
    """
    Run the agent with a user message, incorporating memory context.

    Args:
        agent: The LangGraph agent.
        message: User's message.
        store: Memory store for retrieving context.
        user_id: User identifier.
        thread_id: Conversation thread ID.

    Returns:
        Agent response with messages.
    """
    messages = []

    # Retrieve relevant memories if store is available
    if store:
        memories = await retrieve_user_memories(store, user_id, message)
        system_prompt = build_system_prompt(memories)
    else:
        system_prompt = build_system_prompt()

    messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=message))

    # Run the agent
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }

    result = await agent.ainvoke({"messages": messages}, config=config)

    return result


async def run_agent_stream(
    agent,
    message: str,
    store: BaseStore | None = None,
    user_id: str = "demo_user",
    thread_id: str = "default",
):
    """
    Run the agent with streaming output.

    Args:
        agent: The LangGraph agent.
        message: User's message.
        store: Memory store for retrieving context.
        user_id: User identifier.
        thread_id: Conversation thread ID.

    Yields:
        Streaming events from the agent.
    """
    messages = []

    # Retrieve relevant memories if store is available
    if store:
        memories = await retrieve_user_memories(store, user_id, message)
        system_prompt = build_system_prompt(memories)
    else:
        system_prompt = build_system_prompt()

    messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=message))

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        }
    }

    async for event in agent.astream_events({"messages": messages}, config=config, version="v2"):
        yield event
