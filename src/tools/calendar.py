"""Mock calendar tool for demo purposes."""

from datetime import datetime, timedelta
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel


class BookingResult(BaseModel):
    """Result of a room booking operation."""

    success: bool
    room: str
    date: str
    time: str
    duration: int = 1
    message: str


class QueryResult(BaseModel):
    """Result of a booking query operation."""

    bookings: list[dict]
    message: str


# Simulated room database
AVAILABLE_ROOMS = [
    "1001中会议室",
    "1013小会议室",
    "1015中会议室",
    "1106会议室",
    "1113大会议室",
    "1117小会议室",
    "601会议室",
    "602会议室",
    "603会议室",
]

# In-memory bookings storage (for demo)
_bookings: list[dict] = []


def _normalize_time(value: str) -> str | None:
    import re

    raw = str(value).strip()
    if not raw:
        return None

    # Fast path: HH:MM or HH：MM
    m = re.match(r"^(\d{1,2})\s*[:：]\s*(\d{1,2})$", raw)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None

    # Chinese / am-pm-ish forms: "下午5点", "晚上5点30", "5点", "5点30"
    lowered = raw.lower()
    is_pm = any(k in lowered for k in ["pm", "下午", "晚上"])
    is_am = any(k in lowered for k in ["am", "上午"])

    m = re.search(r"(\d{1,2})(?:\s*[:：]\s*(\d{1,2}))?\s*(?:点|时)?", raw)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or 0)

    if is_pm and hour < 12:
        hour += 12
    if is_am and hour == 12:
        hour = 0

    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


@tool(response_format="content_and_artifact")
def book_meeting_room(
    day: Literal["monday", "tuesday", "wednesday", "thursday", "friday"] | str,
    time_slot: Literal["morning", "afternoon", "evening"] | str = "afternoon",
    start_time: str | None = None,
    duration_hours: int = 1,
    room: str | None = None,
) -> tuple[str, BookingResult]:
    """
    Book a meeting room.

    Args:
        day: Day of the week (e.g., "friday") or a date string.
        time_slot: "morning" (09:00), "afternoon" (14:00), "evening" (17:00),
            or a custom time like "17:30".
        start_time: Optional custom time (HH:MM, 24-hour). If provided, overrides time_slot.
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
    slot_map = {
        "morning": "09:00",
        "afternoon": "14:00",
        "evening": "17:00",
    }

    if start_time:
        normalized = _normalize_time(start_time)
        if not normalized:
            raise ValueError("start_time 必须是有效的 HH:MM（24小时制），例如 17:00 / 09:30")
        start_time = normalized
    else:
        slot_key = str(time_slot).strip().lower()
        if slot_key in slot_map:
            start_time = slot_map[slot_key]
        else:
            normalized = _normalize_time(slot_key)
            if not normalized:
                raise ValueError(
                    "time_slot 仅支持 morning/afternoon/evening，或传入 start_time=HH:MM（24小时制）"
                )
            start_time = normalized

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

    result = BookingResult(
        success=True,
        room=selected_room,
        date=booking["date"],
        time=start_time,
        duration=duration_hours,
        message=(
            f"已成功预订 {selected_room}：{booking['date']} {start_time}，"
            f"时长 {duration_hours} 小时。"
        ),
    )
    # Return (content_for_llm, artifact_for_code)
    return (result.message, result)


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


def generate_ical_content(bookings: list[dict] | None = None) -> str:
    """
    Generate iCal (RFC 5545) content from bookings.

    Args:
        bookings: List of booking dicts. If None, uses module-level _bookings.

    Returns:
        iCal formatted string for all bookings.
    """
    source = bookings if bookings is not None else _bookings
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Digital Employee Demo//Meeting Rooms//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:会议室预订",
    ]

    for i, booking in enumerate(source):
        room = booking.get("room", "Unknown")
        date_str = booking.get("date", "")
        time_str = booking.get("time", "09:00")
        duration = booking.get("duration", 1)

        if not date_str:
            continue

        # Parse date and time
        try:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(hours=duration)
        except ValueError:
            continue

        # Format for iCal (YYYYMMDDTHHMMSS)
        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")
        dtstamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
        uid = f"booking-{i}-{date_str}-{room}@digital-employee-demo"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:会议室预订 - {room}",
            f"LOCATION:{room}",
            "DESCRIPTION:通过数字员工助手预订的会议室",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def get_all_bookings() -> list[dict]:
    """Get all current bookings."""
    return _bookings.copy()


# Export all calendar tools
calendar_tools = [book_meeting_room, query_meeting_rooms, cancel_meeting_room]
