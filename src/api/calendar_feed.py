"""iCal subscription API endpoint for WeCom calendar integration."""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from src.memory.bookings import get_all_bookings_async
from src.tools.calendar import generate_ical_content

app = FastAPI(
    title="Digital Employee Calendar API",
    description="iCal subscription endpoint for WeCom calendar integration",
    version="1.0.0",
)

# Allow CORS for calendar clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/calendar/feed.ics")
async def get_calendar_feed():
    """
    iCal subscription endpoint.

    Returns all meeting room bookings in iCal format.
    WeCom can subscribe to this URL to sync bookings.

    Usage in WeCom:
    1. Go to Calendar > Settings > Subscribe Calendar
    2. Enter this URL: http://<your-server>:8000/calendar/feed.ics
    3. Bookings will sync automatically
    """
    # Read from database (shared across processes)
    bookings = await get_all_bookings_async()
    ical_content = generate_ical_content(bookings)

    return Response(
        content=ical_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=meeting_bookings.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
