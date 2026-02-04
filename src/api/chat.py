"""Chat API for MuseBot integration (OpenAI-compatible)."""

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.services.agent_sync import get_agent, initialize_agent
from src.services.store_sync import connect_store, run_async
from src.agent.graph import retrieve_user_memories
from src.agent.prompts import build_system_prompt
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


app = FastAPI(title="Digital Employee Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "gpt-4"
    messages: list[Message]
    stream: bool = False
    user: str | None = None


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    choices: list[Choice]


@app.on_event("startup")
async def startup():
    """Initialize agent on startup."""
    initialize_agent()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    OpenAI-compatible chat endpoint for MuseBot.

    Extracts user message, runs through LangGraph agent,
    returns response in OpenAI format.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Get the last user message
    user_message = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    # Derive user_id from WeChat user or use default
    user_id = request.user or "wechat_user"
    thread_id = f"wechat_{user_id}"

    store = connect_store()
    agent = get_agent()

    async def _run_agent():
        # Retrieve memories
        memories = await retrieve_user_memories(store, user_id, user_message)

        # Build messages
        system_prompt = build_system_prompt(memories)
        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history from request
        for msg in request.messages[:-1]:  # Exclude last (current) message
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=user_message))

        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
            }
        }

        # Stream and collect response
        full_response = ""
        async for event in agent.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            event_type = event.get("event", "")
            if event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content

        return full_response

    try:
        response_text = run_async(_run_agent())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        choices=[
            Choice(
                index=0,
                message=Message(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ],
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
