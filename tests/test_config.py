"""Configuration loading tests, incl. the timezone resolution that depends
on the `tzdata` package inside the slim Docker image."""

import os

import pytest

from bot.config import _parse_admin_ids, _parse_channel_id, load_config


def test_parse_channel_id():
    assert _parse_channel_id("-1001234567890") == -1001234567890
    assert _parse_channel_id("@my_channel") == "@my_channel"
    assert _parse_channel_id("my_channel") == "@my_channel"


def test_parse_admin_ids():
    assert _parse_admin_ids("1, 2 ,3") == frozenset({1, 2, 3})
    assert _parse_admin_ids("1;2;3") == frozenset({1, 2, 3})
    assert _parse_admin_ids("") == frozenset()


def test_load_config_defaults(monkeypatch):
    env = {
        "BOT_TOKEN": "123:token",
        "CHANNEL_ID": "-1001234567890",
        "ADMIN_IDS": "111,222",
    }
    for key in list(os.environ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    config = load_config()
    assert config.bot_token == "123:token"
    assert config.channel_id == -1001234567890
    assert config.admin_ids == frozenset({111, 222})
    assert config.timezone == "Europe/Moscow"
    assert config.run_mode == "polling"
    # This resolves the IANA database — on python:3.12-slim it requires the
    # `tzdata` package, which is why it's pinned in requirements.txt.
    assert str(config.tz) == "Europe/Moscow"
    assert config.database_url == "sqlite+aiosqlite:///bot.db"


def test_load_config_unknown_timezone_fails(monkeypatch):
    for key in list(os.environ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BOT_TOKEN", "123:token")
    monkeypatch.setenv("CHANNEL_ID", "-1001234567890")
    monkeypatch.setenv("ADMIN_IDS", "111")
    monkeypatch.setenv("TIMEZONE", "Not/AZone")

    with pytest.raises(SystemExit):
        load_config()


def test_load_config_missing_required_fails(monkeypatch):
    for key in list(os.environ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit):
        load_config()
