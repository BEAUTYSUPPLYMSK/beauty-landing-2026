"""Access-control filter: only configured admins may manage content."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.handlers.deps import Deps


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, deps: Deps) -> bool:
        user = event.from_user
        return user is not None and user.id in deps.config.admin_ids
