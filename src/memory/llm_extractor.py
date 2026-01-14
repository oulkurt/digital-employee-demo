"""LLM-driven memory extraction from conversation."""

import asyncio
import json
import logging
import re
from typing import Optional

from langgraph.store.base import BaseStore

from src.llm.chat import get_chat_model
from src.memory.extractor import ExtractedMemory, extract_memories_from_message

logger = logging.getLogger(__name__)

# Valid memory types
VALID_MEMORY_TYPES = {"preference", "interest", "terminology", "fact"}

# LLM extraction prompt
MEMORY_EXTRACTION_PROMPT = """分析以下用户消息，提取值得长期记住的用户信息。

用户消息: {user_message}

提取规则:
1. 只提取明确表达或可合理推断的信息，不要臆测
2. 每条记忆应独立、原子化，便于后续检索
3. 用第三人称描述（"用户偏好..." 而非 "我喜欢..."）
4. 如果没有值得记住的信息，返回空数组 []

记忆类型定义:
- preference: 行为偏好（会议时间、沟通方式、工作习惯）
- interest: 关注领域（行业、技术、话题）
- terminology: 专有术语（项目代号、内部简称、缩写含义）
- fact: 客观事实（职位、团队、负责业务）

输出 JSON 数组，格式如下:
[
  {{"type": "preference", "content": "用户偏好上午开会，下午专注编码"}},
  {{"type": "terminology", "content": "用户提到的 'KP' 指关键绩效项目"}}
]

仅输出 JSON，不要其他文字。"""


def parse_extraction_response(response: str) -> list[dict]:
    """
    Parse LLM response with multiple fallback strategies.

    Args:
        response: Raw LLM response text.

    Returns:
        List of extracted memory dicts, or empty list on failure.
    """
    # Strategy 1: Direct JSON parse
    try:
        result = json.loads(response.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract JSON array from markdown code block
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first [ ... ] pattern
    array_match = re.search(r'\[.*\]', response, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    # All strategies failed
    logger.warning(f"Failed to parse LLM extraction response: {response[:100]}...")
    return []


async def extract_memories_llm(
    user_message: str,
    timeout: float = 15.0,
) -> list[ExtractedMemory]:
    """
    Extract memories from user message using LLM.

    Args:
        user_message: The user's message to analyze.
        timeout: Maximum time to wait for LLM response.

    Returns:
        List of extracted memories.

    Raises:
        asyncio.TimeoutError: If LLM call exceeds timeout.
    """
    llm = get_chat_model(temperature=0, streaming=False)
    prompt = MEMORY_EXTRACTION_PROMPT.format(user_message=user_message)

    # Call LLM with timeout
    response = await asyncio.wait_for(
        llm.ainvoke(prompt),
        timeout=timeout,
    )

    # Parse response
    parsed = parse_extraction_response(response.content)

    # Convert to ExtractedMemory objects
    memories = []
    for item in parsed:
        mem_type = item.get("type", "")
        content = item.get("content", "")

        if mem_type in VALID_MEMORY_TYPES and content and len(content) > 2:
            memories.append(ExtractedMemory(type=mem_type, content=content))

    return memories


async def is_duplicate_memory(
    store: BaseStore,
    user_id: str,
    new_memory: ExtractedMemory,
    similarity_threshold: float = 0.85,
) -> bool:
    """
    Check if memory is duplicate based on semantic similarity.

    Args:
        store: The memory store with vector search.
        user_id: User identifier.
        new_memory: The new memory to check.
        similarity_threshold: Minimum similarity to consider duplicate.

    Returns:
        True if a similar memory already exists.
    """
    namespace = ("user_memories", user_id)

    try:
        # Search for similar memories
        results = await store.asearch(
            namespace,
            query=new_memory.content,
            limit=5,
        )

        for item in results:
            # Check if same type and high similarity
            if item.value.get("type") == new_memory.type:
                # pgvector returns distance, lower is more similar
                # Assuming cosine distance: similarity = 1 - distance
                if hasattr(item, "score") and item.score is not None:
                    similarity = 1.0 - item.score
                    if similarity >= similarity_threshold:
                        return True
    except Exception as e:
        logger.warning(f"Duplicate check failed: {e}")

    return False


async def extract_memories_with_fallback(
    user_message: str,
    store: Optional[BaseStore] = None,
    user_id: Optional[str] = None,
    timeout: float = 15.0,
    deduplicate: bool = True,
) -> list[ExtractedMemory]:
    """
    Extract memories with LLM, falling back to regex on failure.

    Args:
        user_message: The user's message to analyze.
        store: Optional store for deduplication.
        user_id: Optional user ID for deduplication.
        timeout: Maximum time for LLM call.
        deduplicate: Whether to filter duplicate memories.

    Returns:
        List of extracted memories.
    """
    memories = []

    try:
        memories = await extract_memories_llm(user_message, timeout=timeout)
        if memories:
            logger.info(f"LLM extracted {len(memories)} memories")
    except asyncio.TimeoutError:
        logger.warning("LLM extraction timeout, falling back to regex")
        memories = extract_memories_from_message(user_message)
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}, falling back to regex")
        memories = extract_memories_from_message(user_message)

    # Deduplicate if store is available
    if deduplicate and store and user_id and memories:
        unique_memories = []
        for mem in memories:
            if not await is_duplicate_memory(store, user_id, mem):
                unique_memories.append(mem)
            else:
                logger.info(f"Skipped duplicate memory: {mem.content[:30]}...")
        memories = unique_memories

    return memories
