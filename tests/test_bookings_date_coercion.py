import pytest


def test_coerce_iso_date_parses_string():
    from src.memory.bookings import _coerce_iso_date

    d = _coerce_iso_date("2026-02-06")
    assert d.year == 2026 and d.month == 2 and d.day == 6


def test_coerce_iso_date_rejects_empty():
    from src.memory.bookings import _coerce_iso_date

    with pytest.raises(ValueError):
        _coerce_iso_date("")

