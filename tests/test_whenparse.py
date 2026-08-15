from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from bot.core.whenparse import parse_when

MSK = ZoneInfo("Europe/Moscow")
# 2026-08-15 12:00 MSK == 09:00 UTC
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


def test_full_date_time():
    result = parse_when("25.12.2026 18:30", now=NOW, tz=MSK)
    assert result == datetime(2026, 12, 25, 18, 30, tzinfo=MSK)


def test_full_date_in_past_raises():
    with pytest.raises(ValueError):
        parse_when("01.01.2020 10:00", now=NOW, tz=MSK)


def test_day_month_future_this_year():
    result = parse_when("31.12 09:00", now=NOW, tz=MSK)
    assert result.year == 2026


def test_day_month_past_rolls_to_next_year():
    result = parse_when("01.01 10:00", now=NOW, tz=MSK)
    assert result.year == 2027


def test_time_only_today_if_future():
    result = parse_when("18:30", now=NOW, tz=MSK)
    assert (result.year, result.month, result.day) == (2026, 8, 15)
    assert (result.hour, result.minute) == (18, 30)


def test_time_only_rolls_to_tomorrow():
    result = parse_when("09:00", now=NOW, tz=MSK)  # local now is 12:00
    assert result.day == 16


def test_relative_minutes():
    result = parse_when("+30m", now=NOW, tz=MSK)
    assert (result - NOW).total_seconds() == 30 * 60


def test_relative_hours_and_days():
    assert (parse_when("+2h", now=NOW, tz=MSK) - NOW).total_seconds() == 7200
    assert (parse_when("+1d", now=NOW, tz=MSK) - NOW).days == 1


@pytest.mark.parametrize("bad", ["", "abc", "32.13.2026 10:00", "25:99", "+0m", "+5x"])
def test_bad_input_raises(bad):
    with pytest.raises(ValueError):
        parse_when(bad, now=NOW, tz=MSK)
