# Demo Guide

This document provides instructions for running the Digital Employee Memory Demo.

## Prerequisites

1. **Docker** - For PostgreSQL database
2. **uv** - Python package manager (https://docs.astral.sh/uv/)
3. **API Keys** - See `.env.example` for required keys

## Quick Start

### 1. Start Database

```bash
docker-compose up -d
```

Wait for PostgreSQL to be ready (health check will pass).

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
# - OPENROUTER_API_KEY
# - SILICONFLOW_API_KEY
# - TAVILY_API_KEY
```

### 4. Initialize Database

```bash
uv run python -m src.memory.store --init
```

### 5. Run Web UI

```bash
uv run chainlit run app.py
```

Open http://localhost:8000 in your browser.

---

## Demo Scenarios

### Scenario A: User Preference Memory

**Goal**: Demonstrate that the system remembers user preferences.

**Preset Memory**: "User prefers Friday afternoon meetings"

**Demo Steps**:

1. Open the chat interface
2. Type: **"Book a meeting room for me"**
3. Observe: The system should book a Friday afternoon slot automatically

**Expected Response**:
> Based on your preference, I've booked meeting room A301 for Friday afternoon at 14:00. Would you like to adjust the time?

**Key Points to Highlight**:
- No need to specify "Friday" - the system remembers
- Memory was retrieved and applied automatically
- Tool (calendar) was called with the user's preference

---

### Scenario B: Interest-Based News Recommendation

**Goal**: Demonstrate personalized news search based on user interests.

**Preset Memories**:
- "User follows the new energy vehicle industry"
- "User follows AI chip developments"

**Demo Steps**:

1. In the same chat session, type: **"What news should I read today?"**
2. Observe: The system searches for news related to user interests

**Expected Response**:
> Based on your interests, here are today's notable news:
> 1. [EV-related news article]
> 2. [AI chip-related news article]
> ...

**Key Points to Highlight**:
- System retrieved user interests from memory
- Search was tailored to those interests
- Personalized recommendations without explicit request

---

## Troubleshooting

### Database Connection Error

```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart if needed
docker-compose restart postgres
```

### API Key Issues

Verify keys are set correctly:

```bash
uv run python -c "from src.config import get_settings; s = get_settings(); print('OpenRouter:', bool(s.openrouter_api_key)); print('SiliconFlow:', bool(s.siliconflow_api_key)); print('Tavily:', bool(s.tavily_api_key))"
```

### Memory Not Working

Ensure preset memories are loaded:

```python
# In Python shell
import asyncio
from src.memory.store import get_store
from src.memory.preset import load_preset_memories

async def load():
    async with get_store() as store:
        await load_preset_memories(store, user_id="demo_user")
        print("Memories loaded!")

asyncio.run(load())
```

---

## Running Tests

```bash
# Run unit tests (no API keys needed)
uv run pytest tests/test_demo_scenarios.py -v

# Skip integration tests
uv run pytest tests/test_demo_scenarios.py -v -k "not Integration"
```

---

## Architecture Overview

```
User Input
    ↓
Memory Retrieval (pgvector + reranker)
    ↓
Context Building (system prompt + memories)
    ↓
ReAct Agent (LangGraph)
    ↓
Tool Execution (calendar, search)
    ↓
Response Generation
```

See `memory-bank/architecture.md` for details.
