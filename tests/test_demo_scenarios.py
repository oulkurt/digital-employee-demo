"""
Test demo scenarios from PRD.

Scenario A: User preference memory - booking meeting rooms
Scenario B: Interest-based news recommendation
"""

import pytest

from src.agent.graph import create_agent, run_agent
from src.agent.prompts import build_system_prompt
from src.memory.preset import PRESET_MEMORIES, MemoryType, load_preset_memories
from src.tools.calendar import book_meeting_room, query_meeting_rooms


class TestPresetMemories:
    """Test preset memory configuration."""

    def test_preset_memories_exist(self):
        """Verify preset memories are configured."""
        assert len(PRESET_MEMORIES) == 4

    def test_preset_memory_types(self):
        """Verify all memory types are covered."""
        types = {m.type for m in PRESET_MEMORIES}
        assert MemoryType.PREFERENCE in types
        assert MemoryType.INTEREST in types
        assert MemoryType.TERMINOLOGY in types

    def test_friday_preference_exists(self):
        """Verify Friday meeting preference is preset."""
        preferences = [m for m in PRESET_MEMORIES if m.type == MemoryType.PREFERENCE]
        assert any(("周五" in m.content and "下午" in m.content) for m in preferences)

    def test_interest_memories_exist(self):
        """Verify interest memories for news scenario."""
        interests = [m for m in PRESET_MEMORIES if m.type == MemoryType.INTEREST]
        assert len(interests) >= 2
        contents = " ".join(m.content.lower() for m in interests)
        assert ("新能源" in contents) or ("汽车" in contents)
        assert ("ai" in contents) or ("芯片" in contents)


class TestCalendarTool:
    """Test calendar tool functionality."""

    def test_book_meeting_room_friday(self):
        """Test booking a meeting room for Friday."""
        _, result = book_meeting_room.func(
            day="friday",
            time_slot="afternoon",
            duration_hours=1,
            room=None,
        )
        assert result.success is True
        assert result.room is not None
        assert "14:00" in result.time

    def test_book_meeting_room_default(self):
        """Test booking with default time slot."""
        _, result = book_meeting_room.func(
            day="monday",
            time_slot="afternoon",
            duration_hours=1,
            room=None,
        )
        assert result.success is True

    def test_book_meeting_room_evening(self):
        """Test booking a meeting room for 17:00 via evening slot."""
        _, result = book_meeting_room.func(
            day="friday",
            time_slot="evening",
            duration_hours=1,
            room=None,
        )
        assert result.success is True
        assert "17:00" in result.time

    def test_book_meeting_room_custom_time(self):
        """Test booking with custom start_time (HH:MM)."""
        _, result = book_meeting_room.func(
            day="friday",
            time_slot="afternoon",
            start_time="17:30",
            duration_hours=1,
            room=None,
        )
        assert result.success is True
        assert result.time == "17:30"

    def test_book_meeting_room_invalid_time(self):
        """Invalid custom start_time should raise."""
        with pytest.raises(Exception):
            book_meeting_room.func(
                day="friday",
                time_slot="afternoon",
                start_time="25:00",
                duration_hours=1,
                room=None,
            )

    def test_query_meeting_rooms(self):
        """Test querying booked rooms."""
        # First book a room
        book_result = book_meeting_room.invoke({
            "day": "wednesday",
            "time_slot": "morning",
        })

        # Then query
        query_result = query_meeting_rooms.invoke({})
        assert "bookings" in query_result.__dict__ or hasattr(query_result, "bookings")


class TestSystemPrompt:
    """Test system prompt building."""

    def test_build_prompt_without_memories(self):
        """Test prompt building without memories."""
        prompt = build_system_prompt()
        assert "数字员工" in prompt
        assert "会议" in prompt
        assert "记忆" in prompt

    def test_build_prompt_with_memories(self):
        """Test prompt building with memories."""
        memories = [
            {"type": "preference", "content": "User prefers morning meetings"},
            {"type": "interest", "content": "User follows AI news"},
        ]
        prompt = build_system_prompt(memories)
        assert "morning meetings" in prompt
        assert "AI news" in prompt
        assert "[preference]" in prompt
        assert "[interest]" in prompt


class TestScenarioA:
    """
    Scenario A: User preference memory.

    User says "Book a meeting room" without specifying time.
    System should recall preference for Friday afternoon.
    """

    def test_memory_context_includes_friday_preference(self):
        """Verify Friday preference would be in context."""
        # Simulate memory retrieval
        memories = [
            {"type": "preference", "content": "用户偏好在周五下午安排会议。"},
        ]
        prompt = build_system_prompt(memories)

        # The prompt should contain the Friday preference
        assert "周五" in prompt
        assert "下午" in prompt


class TestScenarioB:
    """
    Scenario B: Interest-based news recommendation.

    User asks "What news should I read today?"
    System should search based on user interests (EV, AI chips).
    """

    def test_memory_context_includes_interests(self):
        """Verify interests would be in context."""
        memories = [
            {"type": "interest", "content": "用户关注新能源汽车行业动态。"},
            {"type": "interest", "content": "用户关注AI芯片技术发展。"},
        ]
        prompt = build_system_prompt(memories)

        # The prompt should contain both interests
        assert ("新能源" in prompt) or ("汽车" in prompt)
        assert ("AI" in prompt) or ("芯片" in prompt)


# Integration tests (require database and API keys)
@pytest.mark.skip(reason="Requires database and API keys")
class TestIntegration:
    """Integration tests for full agent flow."""

    @pytest.fixture
    async def agent_with_store(self):
        """Create agent with memory store."""
        from src.memory.store import get_store

        async with get_store() as store:
            await load_preset_memories(store, user_id="test_user")
            agent = create_agent(store=store)
            yield agent, store

    async def test_scenario_a_booking(self, agent_with_store):
        """Test Scenario A: booking with preference."""
        agent, store = agent_with_store

        result = await run_agent(
            agent=agent,
            message="Book a meeting room for me",
            store=store,
            user_id="test_user",
        )

        # Should mention Friday in response
        response_text = result["messages"][-1].content.lower()
        assert "friday" in response_text or "booked" in response_text

    async def test_scenario_b_news(self, agent_with_store):
        """Test Scenario B: news based on interests."""
        agent, store = agent_with_store

        result = await run_agent(
            agent=agent,
            message="What news should I read today?",
            store=store,
            user_id="test_user",
        )

        # Should mention search or news
        response_text = result["messages"][-1].content.lower()
        assert "news" in response_text or "search" in response_text
