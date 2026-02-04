"""PostgreSQL-based bookings storage for cross-process data sharing."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date as Date, datetime
from typing import AsyncGenerator

import asyncpg

from src.config import get_settings


def _coerce_iso_date(value: str | Date) -> Date:
    if isinstance(value, Date):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("date 不能为空（需要 YYYY-MM-DD）")
    return datetime.strptime(text, "%Y-%m-%d").date()


async def _get_conn() -> asyncpg.Connection:
    """Get a database connection."""
    settings = get_settings()
    return await asyncpg.connect(settings.database_url)


async def init_bookings_table() -> None:
    """Initialize the bookings table."""
    conn = await _get_conn()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL DEFAULT 'demo_user',
                room VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                time VARCHAR(10) NOT NULL,
                duration INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bookings_user_date
            ON bookings(user_id, date)
        """)
    finally:
        await conn.close()


async def save_booking(
    room: str,
    date: str,
    time: str,
    duration: int = 1,
    user_id: str = "demo_user",
) -> int:
    """Save a booking to database. Returns booking id."""
    date_obj = _coerce_iso_date(date)
    conn = await _get_conn()
    try:
        result = await conn.fetchval(
            """
            INSERT INTO bookings (user_id, room, date, time, duration)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            user_id,
            room,
            date_obj,
            time,
            duration,
        )
        return result
    finally:
        await conn.close()


async def get_bookings(user_id: str = "demo_user") -> list[dict]:
    """Get all bookings for a user."""
    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT id, room, date, time, duration
            FROM bookings
            WHERE user_id = $1
            ORDER BY date, time
            """,
            user_id,
        )
        return [
            {
                "id": row["id"],
                "room": row["room"],
                "date": row["date"].strftime("%Y-%m-%d"),
                "time": row["time"],
                "duration": row["duration"],
            }
            for row in rows
        ]
    finally:
        await conn.close()


async def get_all_bookings_async() -> list[dict]:
    """Get all bookings (for calendar feed API)."""
    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT id, user_id, room, date, time, duration
            FROM bookings
            ORDER BY date, time
            """
        )
        return [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "room": row["room"],
                "date": row["date"].strftime("%Y-%m-%d"),
                "time": row["time"],
                "duration": row["duration"],
            }
            for row in rows
        ]
    finally:
        await conn.close()


def _run_sync(coro):
    """Run async coroutine synchronously, handling nested event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an event loop - run in a separate thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def get_all_bookings_sync() -> list[dict]:
    """Sync wrapper for get_all_bookings_async."""
    return _run_sync(get_all_bookings_async())


def save_booking_sync(
    room: str,
    date: str,
    time: str,
    duration: int = 1,
    user_id: str = "demo_user",
) -> int:
    """Sync wrapper for save_booking."""
    return _run_sync(save_booking(room, date, time, duration, user_id))


def get_bookings_sync(user_id: str = "demo_user") -> list[dict]:
    """Sync wrapper for get_bookings."""
    return _run_sync(get_bookings(user_id))


async def delete_booking(booking_id: int, user_id: str = "demo_user") -> bool:
    """Delete a booking by id. Returns True if deleted."""
    conn = await _get_conn()
    try:
        result = await conn.execute(
            """
            DELETE FROM bookings
            WHERE id = $1 AND user_id = $2
            """,
            booking_id,
            user_id,
        )
        return result == "DELETE 1"
    finally:
        await conn.close()


if __name__ == "__main__":
    import sys

    if "--init" in sys.argv:
        print("Initializing bookings table...")
        asyncio.run(init_bookings_table())
        print("Done.")
