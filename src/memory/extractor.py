"""Memory extraction from conversation."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langgraph.store.base import BaseStore


@dataclass
class ExtractedMemory:
    """An extracted memory from conversation."""

    type: str
    content: str
    source_text: str | None = None  # Source conversation text
    created_at: str | None = None   # ISO timestamp


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
    source_text: str | None = None,
) -> dict:
    """
    Save a memory to the store.

    Args:
        store: The memory store.
        user_id: User identifier.
        memory: The memory to save.
        source_text: Optional source conversation text (overrides memory.source_text).

    Returns:
        The complete saved memory dict including key.
    """
    namespace = ("user_memories", user_id)
    key = f"learned_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    value = {
        "type": memory.type,
        "content": memory.content,
        "source_text": source_text or memory.source_text,
        "created_at": now,
        "key": key,
    }

    await store.aput(namespace=namespace, key=key, value=value)
    return value


async def get_learned_memories(store: BaseStore, user_id: str) -> list[dict]:
    """
    Get all learned memories for a user.

    Args:
        store: The memory store.
        user_id: User identifier.

    Returns:
        List of learned memory items with full metadata.
    """
    namespace = ("user_memories", user_id)

    # Search all memories
    results = await store.asearch(namespace, query="", limit=100)

    # Filter to learned memories only (exclude presets)
    learned = []
    for item in results:
        if not item.key.startswith("preset_"):
            mem = dict(item.value)
            # Ensure key is always present (compat with old data)
            if "key" not in mem:
                mem["key"] = item.key
            learned.append(mem)

    return learned


async def update_memory(
    store: BaseStore,
    user_id: str,
    key: str,
    new_content: str | None = None,
    new_type: str | None = None,
) -> dict | None:
    """
    Update an existing memory.

    Args:
        store: The memory store.
        user_id: User identifier.
        key: Memory key to update.
        new_content: New content (optional).
        new_type: New type (optional).

    Returns:
        Updated memory dict, or None if not found.
    """
    namespace = ("user_memories", user_id)

    # Get existing
    item = await store.aget(namespace, key)
    if item is None:
        return None

    value = dict(item.value)
    if new_content is not None:
        value["content"] = new_content
    if new_type is not None:
        value["type"] = new_type
    value["updated_at"] = datetime.now(timezone.utc).isoformat()
    value["key"] = key  # ensure key is in value

    await store.aput(namespace=namespace, key=key, value=value)
    return value


async def delete_memory(store: BaseStore, user_id: str, key: str) -> bool:
    """
    Delete a memory by key.

    Args:
        store: The memory store.
        user_id: User identifier.
        key: Memory key to delete.

    Returns:
        True if deleted, False otherwise.
    """
    namespace = ("user_memories", user_id)
    try:
        await store.adelete(namespace, key)
        return True
    except Exception:
        return False
