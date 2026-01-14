"""Synchronous wrapper for LangGraph agent with trace collection."""

import queue
import threading
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.graph import create_agent, retrieve_user_memories
from src.agent.prompts import build_system_prompt
from src.memory.extractor import save_memory
from src.memory.llm_extractor import extract_memories_with_fallback
from src.memory.preset import load_preset_memories
from src.services.store_sync import connect_store, get_event_loop, run_async


@dataclass
class AgentTrace:
    """Collected trace information from agent execution."""

    response: str = ""
    memories: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    rag_results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Global agent instance
_agent = None
_initialized = False


def initialize_agent() -> None:
    """Initialize the store and agent."""
    global _agent, _initialized

    if _initialized:
        return

    store = connect_store()

    # Load preset memories
    run_async(load_preset_memories(store, user_id="demo_user"))

    # Create agent
    _agent = create_agent(store=store)
    _initialized = True


def get_agent():
    """Get the initialized agent."""
    if not _initialized:
        initialize_agent()
    return _agent


def run_agent_with_trace(
    message: str,
    user_id: str = "demo_user",
    thread_id: str = "default",
) -> AgentTrace:
    """
    Run the agent and collect trace information.

    Args:
        message: User's message.
        user_id: User identifier.
        thread_id: Conversation thread ID.

    Returns:
        AgentTrace with response and collected metadata.
    """
    trace = AgentTrace()
    store = connect_store()
    agent = get_agent()

    async def _run():
        # Retrieve memories
        memories = await retrieve_user_memories(store, user_id, message)
        trace.memories = memories
        trace.rag_results = [
            {
                "content": m.get("content", ""),
                "type": m.get("type", "unknown"),
                "score": m.get("rerank_score", 0.0),
            }
            for m in memories
        ]

        # Build messages
        system_prompt = build_system_prompt(memories)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message),
        ]

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            }
        }

        # Stream events and collect trace
        full_response = ""
        async for event in agent.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content

            elif event_type == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                trace.tool_calls.append({
                    "name": tool_name,
                    "input": tool_input,
                    "status": "running",
                    "output": None,
                })

            elif event_type == "on_tool_end":
                tool_output = event.get("data", {}).get("output")
                if trace.tool_calls:
                    trace.tool_calls[-1]["status"] = "completed"
                    trace.tool_calls[-1]["output"] = tool_output

        trace.response = full_response
        return trace

    try:
        return run_async(_run())
    except Exception as e:
        trace.errors.append(str(e))
        trace.response = f"Error: {e}"
        return trace


def run_agent_streaming(
    message: str,
    user_id: str = "demo_user",
    thread_id: str = "default",
    chat_history: list[dict] | None = None,
):
    """
    Generator that yields (event_type, data) tuples for streaming UI updates.

    Args:
        message: Current user message.
        user_id: User identifier.
        thread_id: Conversation thread ID.
        chat_history: Previous messages in the conversation.

    Yields:
        Tuples of (event_type, data) where event_type is one of:
        - "memories": list of retrieved memories
        - "token": text token to append
        - "tool_start": {"name": tool_name, "input": input_data}
        - "tool_end": {"name": tool_name, "output": output_data}
        - "memory_saved": {"content": memory_content, "type": memory_type}
        - "done": final response text
        - "error": error message
    """
    store = connect_store()
    agent = get_agent()

    async def _stream():
        # Retrieve memories first
        memories = await retrieve_user_memories(store, user_id, message)
        yield ("memories", memories)

        # Build messages with chat history
        system_prompt = build_system_prompt(memories)
        messages = [SystemMessage(content=system_prompt)]

        # Add chat history if provided
        if chat_history:
            for msg in chat_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        # Add current message
        messages.append(HumanMessage(content=message))

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            }
        }

        full_response = ""
        current_tool = None

        async for event in agent.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    yield ("token", chunk.content)

            elif event_type == "on_tool_start":
                current_tool = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield ("tool_start", {"name": current_tool, "input": tool_input})

            elif event_type == "on_tool_end":
                tool_output = event.get("data", {}).get("output")
                # Convert Pydantic model to dict for serialization
                if hasattr(tool_output, "model_dump"):
                    tool_output = tool_output.model_dump()
                # Handle ToolMessage wrapper (LangGraph v2 format)
                elif hasattr(tool_output, "content"):
                    # ToolMessage contains content as string repr of Pydantic model
                    # Try to get the actual artifact if available
                    if hasattr(tool_output, "artifact") and tool_output.artifact:
                        if hasattr(tool_output.artifact, "model_dump"):
                            tool_output = tool_output.artifact.model_dump()
                        else:
                            tool_output = tool_output.artifact
                yield ("tool_end", {"name": current_tool, "output": tool_output})

        # Yield done first so user sees complete response
        yield ("done", full_response)

        # Extract and save memories using LLM (after response delivery)
        yield ("memory_extracting", {})
        try:
            extracted = await extract_memories_with_fallback(
                user_message=message,
                store=store,
                user_id=user_id,
                timeout=10.0,
                deduplicate=True,
            )
            for mem in extracted:
                await save_memory(store, user_id, mem)
                yield ("memory_saved", {"content": mem.content, "type": mem.type})
        except Exception as e:
            yield ("memory_extraction_failed", {"reason": str(e)})

    # Use thread + queue for true streaming
    # Events are put into queue immediately as they're produced
    event_queue = queue.Queue()
    _SENTINEL = object()  # Marks end of stream

    main_loop = get_event_loop()

    def run_async_stream():
        """Run async stream in thread, pushing events to queue."""
        async def stream_to_queue():
            try:
                async for event in _stream():
                    event_queue.put(event)
            except Exception as e:
                event_queue.put(("error", str(e)))
            finally:
                event_queue.put(_SENTINEL)

        # Wrap run_until_complete to catch event loop errors
        try:
            main_loop.run_until_complete(stream_to_queue())
        except Exception as e:
            # Ensure error and sentinel are queued even if run_until_complete fails
            import traceback
            traceback.print_exc()
            event_queue.put(("error", f"Event loop error: {e}"))
            event_queue.put(_SENTINEL)

    # Start streaming in background thread
    stream_thread = threading.Thread(target=run_async_stream, daemon=True)
    stream_thread.start()

    # Yield events as they arrive from the queue
    while True:
        try:
            event = event_queue.get(timeout=60.0)  # 60s timeout per event
            if event is _SENTINEL:
                break
            yield event
        except queue.Empty:
            yield ("error", "Stream timeout")
            break
