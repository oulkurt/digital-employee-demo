import pytest


class _FakeToolMessage:
    def __init__(self, content=None, artifact=None):
        self.content = content
        self.artifact = artifact


@pytest.mark.parametrize(
    "content",
    [
        '{"bookings":[{"room":"1001中会议室","date":"2026-02-03","time":"09:00"}],"message":"Found 1 booking(s)."}',
        "{'bookings':[{'room':'1001中会议室','date':'2026-02-03','time':'09:00'}],'message':'Found 1 booking(s).'}",
        "QueryResult(bookings=[{'room': '1001中会议室', 'date': '2026-02-03', 'time': '09:00'}], message='Found 1 booking(s).')",
    ],
)
def test_normalize_tool_output_parses_bookings_to_list(content):
    from src.services.agent_sync import normalize_tool_output

    out = normalize_tool_output(_FakeToolMessage(content=content, artifact=None))
    assert isinstance(out, dict)
    assert isinstance(out.get("bookings"), list)
    assert out["bookings"][0]["room"] == "1001中会议室"

