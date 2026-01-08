"""Chainlit Web UI entry point for Digital Employee Demo."""

import asyncio

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadDict

from src.agent.graph import create_agent, run_agent_stream
from src.config import get_settings
from src.memory.preset import load_preset_memories
from src.memory.store import get_store


# Global store reference - keep context manager alive
_store_cm = None
_store = None
_agent = None
_init_lock = asyncio.Lock()
_initialized = False


@cl.data_layer
def get_data_layer():
    """Configure SQLAlchemy data layer for chat history persistence."""
    settings = get_settings()
    # Convert postgresql:// to postgresql+asyncpg://
    conninfo = settings.database_url
    if conninfo.startswith("postgresql://"):
        conninfo = conninfo.replace("postgresql://", "postgresql+asyncpg://", 1)
    return SQLAlchemyDataLayer(conninfo=conninfo)


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Simple password authentication for demo."""
    # Demo credentials - in production use proper authentication
    if (username, password) == ("demo", "demo"):
        return cl.User(
            identifier="demo_user",
            metadata={"role": "user", "provider": "credentials"},
        )
    elif (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin",
            metadata={"role": "admin", "provider": "credentials"},
        )
    return None


async def _ensure_initialized():
    """Ensure store and agent are initialized (thread-safe)."""
    global _store_cm, _store, _agent, _initialized

    if _initialized:
        return

    async with _init_lock:
        # Double-check after acquiring lock
        if _initialized:
            return

        # Create store context - keep reference to prevent GC
        _store_cm = get_store()
        _store = await _store_cm.__aenter__()

        # Load preset memories for demo
        await load_preset_memories(_store, user_id="demo_user")

        # Create agent
        _agent = create_agent(store=_store)
        _initialized = True


@cl.set_starters
async def set_starters():
    """Set up starter prompts for quick actions."""
    return [
        cl.Starter(
            label="预订会议室",
            message="帮我订个会议室",
            icon="/public/calendar.svg",
        ),
        cl.Starter(
            label="查询会议室",
            message="查询我预订的会议室",
            icon="/public/search.svg",
        ),
        cl.Starter(
            label="今日新闻",
            message="今天有什么值得看的新闻？",
            icon="/public/news.svg",
        ),
        cl.Starter(
            label="AI 资讯",
            message="帮我搜索最新的 AI 行业资讯",
            icon="/public/ai.svg",
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session."""
    # Ensure global initialization is complete
    await _ensure_initialized()

    # Get user from session
    user = cl.user_session.get("user")
    user_id = user.identifier if user else "demo_user"

    # Store in session
    cl.user_session.set("store", _store)
    cl.user_session.set("agent", _agent)
    cl.user_session.set("user_id", user_id)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    """Resume a previous chat session."""
    # Ensure global initialization is complete
    await _ensure_initialized()

    # Get user from session
    user = cl.user_session.get("user")
    user_id = user.identifier if user else "demo_user"

    # Store in session
    cl.user_session.set("store", _store)
    cl.user_session.set("agent", _agent)
    cl.user_session.set("user_id", user_id)

    # Note: Chainlit automatically restores message history to UI via
    # context.emitter.resume_thread(thread) in socket.py after this callback


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages."""
    # Ensure initialization (in case on_chat_start was skipped)
    await _ensure_initialized()

    store = cl.user_session.get("store") or _store
    agent = cl.user_session.get("agent") or _agent
    user_id = cl.user_session.get("user_id") or "demo_user"

    if not agent:
        await cl.Message(content="助手未初始化，请刷新页面重试。").send()
        return

    # Create response message for streaming
    # Force parent_id=None after creation to ensure this is a root-level message
    # (Chainlit's __post_init__ may set parent_id from local_steps context)
    response_msg = cl.Message(content="")
    response_msg.parent_id = None
    await response_msg.send()

    # Collect the full response
    full_response = ""

    try:
        async for event in run_agent_stream(
            agent=agent,
            message=message.content,
            store=store,
            user_id=user_id,
            thread_id=cl.context.session.thread_id,
        ):
            # Handle different event types
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    await response_msg.stream_token(chunk.content)

            elif event["event"] == "on_tool_start":
                tool_name = event.get("name", "unknown")
                await cl.Message(
                    content=f"🔧 正在使用工具：**{tool_name}**",
                    author="system",
                ).send()

            elif event["event"] == "on_tool_end":
                pass  # Tool completed

    except Exception as e:
        full_response = f"发生错误：{str(e)}"
        await response_msg.stream_token(full_response)

    # Finalize the message
    response_msg.content = full_response
    await response_msg.update()


@cl.on_chat_end
async def on_chat_end():
    """Clean up when chat ends."""
    # Note: Store cleanup is handled at app shutdown
    pass


if __name__ == "__main__":
    # For development: run with `chainlit run app.py`
    pass
