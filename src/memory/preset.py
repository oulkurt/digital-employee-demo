"""Preset memories for demo purposes."""

from dataclasses import dataclass
from enum import Enum


class MemoryType(str, Enum):
    """Types of user memories."""

    PREFERENCE = "preference"
    INTEREST = "interest"
    TERMINOLOGY = "terminology"
    FACT = "fact"


@dataclass
class PresetMemory:
    """A preset memory entry."""

    type: MemoryType
    content: str


PRESET_MEMORIES: list[PresetMemory] = [
    PresetMemory(
        type=MemoryType.PREFERENCE,
        content="用户偏好在周五下午安排会议。",
    ),
    PresetMemory(
        type=MemoryType.INTEREST,
        content="用户关注新能源汽车行业动态。",
    ),
    PresetMemory(
        type=MemoryType.INTEREST,
        content="用户关注AI芯片技术发展。",
    ),
    PresetMemory(
        type=MemoryType.TERMINOLOGY,
        content="用户把X项目称为'那个烂摊子'。",
    ),
]


async def load_preset_memories(store, user_id: str = "demo_user") -> None:
    """
    Load preset memories into the store for a user.

    Args:
        store: AsyncPostgresStore instance.
        user_id: User identifier.
    """
    namespace = ("user_memories", user_id)

    for i, memory in enumerate(PRESET_MEMORIES):
        await store.aput(
            namespace=namespace,
            key=f"preset_{i}",
            value={
                "type": memory.type.value,
                "content": memory.content,
            },
        )
