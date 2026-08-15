"""Normalization of DATABASE_URL values for the async SQLAlchemy engine."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DEFAULT_SQLITE = "sqlite+aiosqlite:///bot.db"

# Query parameters that libpq understands but asyncpg does not accept via URL.
_STRIP_PARAMS = {"sslmode", "options", "target_session_attrs", "channel_binding"}


def normalize_database_url(raw: str | None) -> str:
    """Convert a Railway/Heroku-style DATABASE_URL to an async SQLAlchemy URL.

    - empty/None            -> local SQLite file (development fallback)
    - postgres://...        -> postgresql+asyncpg://...
    - postgresql://...      -> postgresql+asyncpg://...
    - sqlite:///...         -> sqlite+aiosqlite:///...
    - libpq-only query params (sslmode etc.) are stripped for asyncpg.
    """
    if not raw or not raw.strip():
        return _DEFAULT_SQLITE
    url = raw.strip()

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("sqlite:///"):
        url = "sqlite+aiosqlite:///" + url[len("sqlite:///"):]

    if url.startswith("postgresql+asyncpg://"):
        scheme, netloc, path, query, fragment = urlsplit(url)
        if query:
            kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True)
                    if k not in _STRIP_PARAMS]
            url = urlunsplit((scheme, netloc, path, urlencode(kept), fragment))
    return url
