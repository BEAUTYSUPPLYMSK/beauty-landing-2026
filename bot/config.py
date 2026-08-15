"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from bot.core.dburl import normalize_database_url


@dataclass(slots=True)
class Config:
    bot_token: str
    channel_id: int | str
    admin_ids: frozenset[int]
    database_url: str
    timezone: str
    run_mode: str
    webhook_url: str
    webhook_secret: str = field(default="")
    port: int = 8080

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def _parse_channel_id(raw: str) -> int | str:
    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        return raw if raw.startswith("@") else "@" + raw


def _parse_admin_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            ids.add(int(chunk))
    return frozenset(ids)


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise SystemExit("BOT_TOKEN is not set. See .env.example / README.md")

    channel_raw = os.getenv("CHANNEL_ID", "").strip()
    if not channel_raw:
        raise SystemExit("CHANNEL_ID is not set. See .env.example / README.md")

    admins_raw = os.getenv("ADMIN_IDS", "").strip()
    if not admins_raw:
        raise SystemExit("ADMIN_IDS is not set. See .env.example / README.md")
    try:
        admin_ids = _parse_admin_ids(admins_raw)
    except ValueError:
        raise SystemExit("ADMIN_IDS must be comma-separated numeric Telegram user IDs") from None
    if not admin_ids:
        raise SystemExit("ADMIN_IDS is empty")

    run_mode = os.getenv("RUN_MODE", "polling").strip().lower() or "polling"
    if run_mode not in {"polling", "webhook"}:
        raise SystemExit("RUN_MODE must be 'polling' or 'webhook'")

    webhook_url = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
    if run_mode == "webhook" and not webhook_url:
        raise SystemExit("WEBHOOK_URL is required when RUN_MODE=webhook")

    timezone = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        ZoneInfo(timezone)
    except Exception:
        raise SystemExit(f"Unknown TIMEZONE: {timezone!r} (use IANA names, e.g. Europe/Moscow)") from None

    return Config(
        bot_token=bot_token,
        channel_id=_parse_channel_id(channel_raw),
        admin_ids=admin_ids,
        database_url=normalize_database_url(os.getenv("DATABASE_URL")),
        timezone=timezone,
        run_mode=run_mode,
        webhook_url=webhook_url,
        webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
        port=int(os.getenv("PORT", "8080")),
    )
