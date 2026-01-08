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
        assert any("friday" in m.content.lower() for m in preferences)

    def test_interest_memories_exist(self):
        """Verify interest memories for news scenario."""
        interests = [m for m in PRESET_MEMORIES if m.type == MemoryType.INTEREST]
        assert len(interests) >= 2
        contents = " ".join(m.content.lower() for m in interests)
        assert "energy" in contents or "vehicle" in contents
        assert "ai" in contents or "chip" in contents


class TestCalendarTool:
    """Test calendar tool functionality."""

    def test_book_meeting_room_friday(self):
        """Test booking a meeting room for Friday."""
        result = book_meeting_room.invoke({
            "day": "friday",
            "time_slot": "afternoon",
        })
        assert result.success is True
        assert result.room is not None
        assert "14:00" in result.time

    def test_book_meeting_room_default(self):
        """Test booking with default time slot."""
        result = book_meeting_room.invoke({
            "day": "monday",
        })
        assert result.success is True

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
        assert "digital employee" in prompt.lower()
        assert "meeting" in prompt.lower()
        assert "memory" in prompt.lower()

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
            {"type": "preference", "content": "User prefers Friday afternoon meetings"},
        ]
        prompt = build_system_prompt(memories)

        # The prompt should contain the Friday preference
        assert "friday" in prompt.lower()
        assert "afternoon" in prompt.lower()


class TestScenarioB:
    """
    Scenario B: Interest-based news recommendation.

    User asks "What news should I read today?"
    System should search based on user interests (EV, AI chips).
    """

    def test_memory_context_includes_interests(self):
        """Verify interests would be in context."""
        memories = [
            {"type": "interest", "content": "User follows new energy vehicles"},
            {"type": "interest", "content": "User follows AI chip developments"},
        ]
        prompt = build_system_prompt(memories)

        # The prompt should contain both interests
        assert "energy" in prompt.lower() or "vehicle" in prompt.lower()
        assert "ai" in prompt.lower() or "chip" in prompt.lower()


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
