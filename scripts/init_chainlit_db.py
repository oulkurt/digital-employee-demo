"""Initialize Chainlit database schema for SQLAlchemy data layer."""

import asyncio

import asyncpg

from src.config import get_settings

CHAINLIT_SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    "id" UUID PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL,
    "createdAt" TEXT
);

-- Threads table
CREATE TABLE IF NOT EXISTS threads (
    "id" UUID PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" UUID,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

-- Steps table
CREATE TABLE IF NOT EXISTS steps (
    "id" UUID PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" UUID NOT NULL,
    "parentId" UUID,
    "disableFeedback" BOOLEAN NOT NULL DEFAULT false,
    "streaming" BOOLEAN NOT NULL DEFAULT false,
    "waitForAnswer" BOOLEAN DEFAULT false,
    "isError" BOOLEAN DEFAULT false,
    "metadata" JSONB,
    "tags" TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "language" TEXT,
    "indent" INT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Elements table
CREATE TABLE IF NOT EXISTS elements (
    "id" UUID PRIMARY KEY,
    "threadId" UUID,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "page" INT,
    "language" TEXT,
    "forId" UUID,
    "mime" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Feedbacks table
CREATE TABLE IF NOT EXISTS feedbacks (
    "id" UUID PRIMARY KEY,
    "forId" UUID NOT NULL,
    "threadId" UUID NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads("userId");
CREATE INDEX IF NOT EXISTS idx_threads_user_identifier ON threads("userIdentifier");
CREATE INDEX IF NOT EXISTS idx_steps_thread_id ON steps("threadId");
CREATE INDEX IF NOT EXISTS idx_elements_thread_id ON elements("threadId");
CREATE INDEX IF NOT EXISTS idx_feedbacks_thread_id ON feedbacks("threadId");
"""


async def init_chainlit_schema():
    """Initialize Chainlit database schema."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(CHAINLIT_SCHEMA)
        print("Chainlit database schema initialized successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_chainlit_schema())
