"""Mock calendar tool for demo purposes."""

from datetime import datetime, timedelta
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class BookingResult(BaseModel):
    """Result of a room booking operation."""

    success: bool
    room: str
    date: str
    time: str
    message: str


class QueryResult(BaseModel):
    """Result of a booking query operation."""

    bookings: list[dict]
    message: str


# Simulated room database
AVAILABLE_ROOMS = ["A301", "A302", "B201", "B202", "C101"]

# In-memory bookings storage (for demo)
_bookings: list[dict] = []


@tool
def book_meeting_room(
    day: Literal["monday", "tuesday", "wednesday", "thursday", "friday"] | str,
    time_slot: Literal["morning", "afternoon"] = "afternoon",
    duration_hours: int = 1,
    room: str | None = None,
) -> BookingResult:
    """
    Book a meeting room.

    Args:
        day: Day of the week (e.g., "friday") or a date string.
        time_slot: "morning" (9:00) or "afternoon" (14:00).
        duration_hours: Duration in hours (default 1).
        room: Specific room to book, or None for auto-assignment.

    Returns:
        BookingResult with booking details.
    """
    # Calculate the target date
    today = datetime.now()
    day_mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    if day.lower() in day_mapping:
        target_weekday = day_mapping[day.lower()]
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)
    else:
        target_date = today + timedelta(days=1)

    # Determine time
    start_time = "09:00" if time_slot == "morning" else "14:00"

    # Select room
    selected_room = room if room in AVAILABLE_ROOMS else AVAILABLE_ROOMS[0]

    # Create booking
    booking = {
        "room": selected_room,
        "date": target_date.strftime("%Y-%m-%d"),
        "time": start_time,
        "duration": duration_hours,
    }
    _bookings.append(booking)

    return BookingResult(
        success=True,
        room=selected_room,
        date=booking["date"],
        time=start_time,
        message=f"Successfully booked {selected_room} on {booking['date']} at {start_time} for {duration_hours} hour(s).",
    )


@tool
def query_meeting_rooms(
    date: str | None = None,
) -> QueryResult:
    """
    Query booked meeting rooms.

    Args:
        date: Optional date filter (YYYY-MM-DD format).

    Returns:
        QueryResult with list of bookings.
    """
    if date:
        filtered = [b for b in _bookings if b["date"] == date]
    else:
        filtered = _bookings.copy()

    if not filtered:
        return QueryResult(
            bookings=[],
            message="No bookings found.",
        )

    return QueryResult(
        bookings=filtered,
        message=f"Found {len(filtered)} booking(s).",
    )


@tool
def cancel_meeting_room(
    room: str,
    date: str,
) -> dict:
    """
    Cancel a meeting room booking.

    Args:
        room: Room name (e.g., "A301").
        date: Date of the booking (YYYY-MM-DD format).

    Returns:
        Result with success status and message.
    """
    global _bookings

    original_count = len(_bookings)
    _bookings = [
        b for b in _bookings if not (b["room"] == room and b["date"] == date)
    ]

    if len(_bookings) < original_count:
        return {
            "success": True,
            "message": f"Cancelled booking for {room} on {date}.",
        }
    else:
        return {
            "success": False,
            "message": f"No booking found for {room} on {date}.",
        }


# Export all calendar tools
calendar_tools = [book_meeting_room, query_meeting_rooms, cancel_meeting_room]
