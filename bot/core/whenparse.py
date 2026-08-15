"""Parsing of human-entered schedule times (pure logic).

Accepted formats (times are interpreted in the configured timezone):

    25.12.2026 18:30   — full date and time
    25.12 18:30        — nearest future occurrence of that day
    18:30              — today, or tomorrow if already past
    +30m / +2h / +1d   — relative offsets from now
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_RELATIVE_RE = re.compile(r"^\+\s*(\d+)\s*([mhd])$", re.IGNORECASE)
_FULL_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})$")
_DAYMONTH_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")

FORMAT_HINT = (
    "Форматы: <code>25.12.2026 18:30</code>, <code>25.12 18:30</code>, "
    "<code>18:30</code> или <code>+30m</code> / <code>+2h</code> / <code>+1d</code>"
)


def parse_when(text: str, *, now: datetime, tz: ZoneInfo) -> datetime:
    """Parse `text` into an aware datetime strictly in the future.

    `now` must be timezone-aware. Raises ValueError on bad input or past times.
    """
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    local_now = now.astimezone(tz)
    text = text.strip()

    match = _RELATIVE_RE.match(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        if amount <= 0:
            raise ValueError("Интервал должен быть больше нуля.")
        delta = {"m": timedelta(minutes=amount),
                 "h": timedelta(hours=amount),
                 "d": timedelta(days=amount)}[unit]
        return local_now + delta

    match = _FULL_RE.match(text)
    if match:
        day, month, year, hour, minute = map(int, match.groups())
        result = _build(year, month, day, hour, minute, tz)
        _ensure_future(result, local_now)
        return result

    match = _DAYMONTH_RE.match(text)
    if match:
        day, month, hour, minute = map(int, match.groups())
        result = _build(local_now.year, month, day, hour, minute, tz)
        if result <= local_now:
            result = _build(local_now.year + 1, month, day, hour, minute, tz)
        return result

    match = _TIME_RE.match(text)
    if match:
        hour, minute = map(int, match.groups())
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Некорректное время.")
        result = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if result <= local_now:
            result += timedelta(days=1)
        return result

    raise ValueError("Не удалось распознать дату/время.")


def _build(year: int, month: int, day: int, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    try:
        return datetime(year, month, day, hour, minute, tzinfo=tz)
    except ValueError as exc:
        raise ValueError("Такой даты не существует.") from exc


def _ensure_future(value: datetime, local_now: datetime) -> None:
    if value <= local_now:
        raise ValueError("Это время уже в прошлом.")
