"""Shared dependencies injected into handlers via dispatcher workflow data."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config import Config
from bot.db.repo import Repo
from bot.services.publisher import Publisher


@dataclass(slots=True)
class Deps:
    config: Config
    repo: Repo
    publisher: Publisher
