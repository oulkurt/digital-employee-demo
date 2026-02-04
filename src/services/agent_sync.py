"""Synchronous wrapper for LangGraph agent with trace collection."""

import ast
import json
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


class ThoughtTagFilter:
    """
    Streaming-safe filter to remove hidden reasoning tags and their content.

    Some model providers emit `<think>...</think>` or `<analysis>...</analysis>` in the output.
    This filter strips them so the UI only shows user-facing content.
    """

    def __init__(self, tags: tuple[str, ...] = ("think", "analysis")) -> None:
        self._tags = tags
        self._in_tag: str | None = None
        self._carry: str = ""

    def feed(self, text: str) -> str:
        if not text:
            return ""

        s = self._carry + text
        self._carry = ""
        out: list[str] = []
        i = 0

        def split_partial_tag(src: str) -> tuple[str, str]:
            last_lt = src.rfind("<")
            if last_lt == -1:
                return src, ""
            tail = src[last_lt:]
            for t in self._tags:
                if f"<{t}>".startswith(tail) or f"</{t}>".startswith(tail):
                    return src[:last_lt], tail
            return src, ""

        while i < len(s):
            if self._in_tag:
                close = f"</{self._in_tag}>"
                j = s.find(close, i)
                if j == -1:
                    keep = len(close) - 1
                    self._carry = s[-keep:] if keep > 0 and len(s) >= keep else s
                    return "".join(out)
                i = j + len(close)
                self._in_tag = None
                continue

            # Find earliest open/close markers among known tags.
            best_pos = None
            best_kind = None
            best_tag = None
            for t in self._tags:
                op = s.find(f"<{t}>", i)
                cp = s.find(f"</{t}>", i)
                if op != -1 and (best_pos is None or op < best_pos):
                    best_pos, best_kind, best_tag = op, "open", t
                if cp != -1 and (best_pos is None or cp < best_pos):
                    best_pos, best_kind, best_tag = cp, "close", t

            if best_pos is None:
                remaining = s[i:]
                safe, carry = split_partial_tag(remaining)
                out.append(safe)
                self._carry = carry
                break

            out.append(s[i:best_pos])
            if best_kind == "open":
                i = best_pos + len(f"<{best_tag}>")
                self._in_tag = best_tag
            else:
                # Stray closing tag; drop it.
                i = best_pos + len(f"</{best_tag}>")

        return "".join(out)


class FinalAnswerFilter:
    """
    Streaming-safe filter that only emits content inside `<final>...</final>`.

    Also strips `<think>...</think>` and `<analysis>...</analysis>` blocks if present.
    If the model doesn't follow the tags, the caller should fall back to another display strategy.
    """

    def __init__(
        self,
        *,
        hidden_tags: tuple[str, ...] = ("think", "analysis"),
        final_tag: str = "final",
    ) -> None:
        self._hidden_filter = ThoughtTagFilter(tags=hidden_tags)
        self._final_tag = final_tag
        self._carry: str = ""
        self._in_final = False
        self._done = False
        self.seen_final = False

    def feed(self, text: str) -> str:
        if self._done or not text:
            return ""

        # First strip hidden tags (think/analysis). This also handles partial tag carries.
        stripped = self._hidden_filter.feed(text)
        if not stripped:
            return ""

        s = self._carry + stripped
        self._carry = ""
        out: list[str] = []

        open_tag = f"<{self._final_tag}>"
        close_tag = f"</{self._final_tag}>"

        i = 0
        while i < len(s):
            if not self._in_final:
                j = s.find(open_tag, i)
                if j == -1:
                    # Keep potential partial "<final>" at end.
                    tail = s[i:]
                    last_lt = tail.rfind("<")
                    if last_lt != -1:
                        possible = tail[last_lt:]
                        if open_tag.startswith(possible):
                            self._carry = possible
                    return "".join(out)
                self._in_final = True
                self.seen_final = True
                i = j + len(open_tag)
                continue

            # In final: emit until close tag.
            k = s.find(close_tag, i)
            if k == -1:
                chunk = s[i:]
                # Avoid emitting a partial closing tag fragment at the end.
                last_lt = chunk.rfind("<")
                if last_lt != -1:
                    possible = chunk[last_lt:]
                    if close_tag.startswith(possible):
                        out.append(chunk[:last_lt])
                        self._carry = possible
                        return "".join(out)
                out.append(chunk)
                return "".join(out)

            out.append(s[i:k])
            i = k + len(close_tag)
            self._in_final = False
            self._done = True
            break

        return "".join(out)


def strip_hidden_reasoning(text: str) -> str:
    """Non-streaming helper to remove `<think>/<analysis>` blocks from a whole string."""
    f = ThoughtTagFilter()
    return f.feed(text)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return text


def _try_parse_structured(text: str):
    text = _strip_code_fences(text)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    if text[0] in "[{":
        try:
            return ast.literal_eval(text)
        except Exception:
            return None
    return None


def _parse_tool_content(content_str: str) -> dict:
    """
    Parse tool output from ToolMessage.content into a structured dict when possible.

    This keeps the UI stable even when the tool output is delivered as a string.
    """
    content_str = _strip_code_fences(str(content_str).strip())
    parsed = _try_parse_structured(content_str)
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list):
        return {"data": parsed}

    tool_output: dict = {"raw_content": content_str}

    # Fallback: parse "key=value" pairs from repr-like strings (e.g., Pydantic repr).
    import re

    pairs = re.findall(
        r"(\w+)=("  # key=
        r"\[[\s\S]*?\]"  # list literal
        r"|\{[\s\S]*?\}"  # dict literal
        r"|[^,)]+"  # scalar up to comma/close-paren
        r")",
        content_str,
    )
    for key, raw_value in pairs:
        value = raw_value.strip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1]

        lowered = value.lower()
        if lowered == "true":
            tool_output[key] = True
            continue
        if lowered == "false":
            tool_output[key] = False
            continue
        if lowered in {"none", "null"}:
            tool_output[key] = None
            continue

        parsed_value = _try_parse_structured(value)
        tool_output[key] = parsed_value if parsed_value is not None else value

    return tool_output


def normalize_tool_output(tool_output):
    """
    Normalize tool output into a JSON-serializable structure for Streamlit.

    Handles LangGraph v2 ToolMessage wrappers and common string encodings.
    """
    if tool_output is None:
        return None

    # Handle ToolMessage wrapper first (LangGraph v2 format)
    if hasattr(tool_output, "artifact"):
        artifact = getattr(tool_output, "artifact", None)
        if artifact is not None:
            if hasattr(artifact, "model_dump"):
                return artifact.model_dump()
            if isinstance(artifact, dict):
                return artifact
            return {"artifact": str(artifact)}

        content = getattr(tool_output, "content", None)
        if content is not None:
            return _parse_tool_content(str(content))

    # Convert Pydantic model to dict for serialization
    if hasattr(tool_output, "model_dump"):
        return tool_output.model_dump()

    # Raw dict/list/str already fine
    if isinstance(tool_output, (dict, list, str, int, float, bool)):
        return tool_output

    return {"raw_output": str(tool_output)}


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
        final_filter = FinalAnswerFilter()
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
        raw_response = ""
        async for event in agent.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    raw_response += chunk.content
                    visible = final_filter.feed(chunk.content)
                    if visible:
                        full_response += visible

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
        if not full_response and raw_response:
            trace.response = strip_hidden_reasoning(raw_response)
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
        final_filter = FinalAnswerFilter()
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
        raw_response = ""
        current_tool = None

        async for event in agent.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            event_type = event.get("event", "")

            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    raw_response += chunk.content
                    visible = final_filter.feed(chunk.content)
                    if visible:
                        full_response += visible
                        yield ("token", visible)

            elif event_type == "on_tool_start":
                current_tool = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield ("tool_start", {"name": current_tool, "input": tool_input})

            elif event_type == "on_tool_end":
                tool_output = normalize_tool_output(event.get("data", {}).get("output"))

                yield ("tool_end", {"name": current_tool, "output": tool_output})

        # Yield done first so user sees complete response
        if not full_response and raw_response:
            yield ("done", strip_hidden_reasoning(raw_response))
        else:
            yield ("done", full_response)

        # Extract and save memories using LLM (after response delivery)
        yield ("memory_extracting", {})
        try:
            extracted = await extract_memories_with_fallback(
                user_message=message,
                store=store,
                user_id=user_id,
                timeout=15.0,
                deduplicate=True,
            )
            for mem in extracted:
                saved = await save_memory(store, user_id, mem, source_text=message)
                yield ("memory_saved", saved)  # Return full dict with key
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
