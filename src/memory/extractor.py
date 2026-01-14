"""Memory extraction from conversation."""

import re
import uuid
from dataclasses import dataclass

from langgraph.store.base import BaseStore


@dataclass
class ExtractedMemory:
    """An extracted memory from conversation."""

    type: str
    content: str


# Patterns that indicate user preferences
# Using non-greedy matching with length limits to avoid capturing too much text
PREFERENCE_PATTERNS = [
    r"记住[我]?(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"我(喜欢|偏好|习惯|倾向于?)(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"以后(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"下次(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"我?(现在)?偏好(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"改成(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"我?(想|要|希望)(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:请|麻烦)?记得?(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:请|麻烦)?帮我记住(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:以后|下次)?不要忘记(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:能|可以)?把(.{2,30}?)记下来(?:[，。！？,\.!?]|$)",
    # New patterns for preference changes
    r"不再(?:是)?(.{2,30}?)了(?:[，。！？,\.!?]|$)",
    r"现在(?:是|习惯|喜欢)?(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:从现在起|今后)(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"换成(.{2,30}?)(?:[，。！？,\.!?]|$)",
]

# Patterns that indicate user interests
INTEREST_PATTERNS = [
    r"我(对|关注|感兴趣)(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"帮我关注(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:想|要)?了解(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"想知道(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"关注一下(.{2,30}?)(?:[，。！？,\.!?]|$)",
    r"(?:请|麻烦)?推荐(.{2,30}?)(?:[，。！？,\.!?]|$)",
]


def extract_memories_from_message(user_message: str) -> list[ExtractedMemory]:
    """
    Extract potential memories from user message.

    Args:
        user_message: The user's message.

    Returns:
        List of extracted memories.
    """
    memories = []

    # Check preference patterns
    for pattern in PREFERENCE_PATTERNS:
        matches = re.findall(pattern, user_message, re.IGNORECASE)
        if matches:
            # Build memory content from the match
            if isinstance(matches[0], tuple):
                content = "".join(matches[0])
            else:
                content = matches[0]

            # Clean up the content
            content = content.strip("，。！？,.!?")
            if content and len(content) > 2:
                memories.append(ExtractedMemory(
                    type="preference",
                    content=f"用户{content}",
                ))
                break  # Only extract one preference per message

    # Check interest patterns
    for pattern in INTEREST_PATTERNS:
        matches = re.findall(pattern, user_message, re.IGNORECASE)
        if matches:
            if isinstance(matches[0], tuple):
                content = "".join(matches[0])
            else:
                content = matches[0]

            content = content.strip("，。！？,.!?")
            if content and len(content) > 2:
                memories.append(ExtractedMemory(
                    type="interest",
                    content=f"用户{content}",
                ))
                break

    return memories


async def save_memory(
    store: BaseStore,
    user_id: str,
    memory: ExtractedMemory,
) -> str:
    """
    Save a memory to the store.

    Args:
        store: The memory store.
        user_id: User identifier.
        memory: The memory to save.

    Returns:
        The key of the saved memory.
    """
    namespace = ("user_memories", user_id)
    key = f"learned_{uuid.uuid4().hex[:8]}"

    await store.aput(
        namespace=namespace,
        key=key,
        value={
            "type": memory.type,
            "content": memory.content,
        },
    )

    return key


async def get_learned_memories(store: BaseStore, user_id: str) -> list[dict]:
    """
    Get all learned memories for a user.

    Args:
        store: The memory store.
        user_id: User identifier.

    Returns:
        List of learned memory items.
    """
    namespace = ("user_memories", user_id)

    # Search all memories
    results = await store.asearch(namespace, query="", limit=100)

    # Filter to learned memories only (exclude presets)
    learned = []
    for item in results:
        if not item.key.startswith("preset_"):
            learned.append(item.value)

    return learned
