"""Persistent post scheduler.

Scheduling state lives in the `posts` table (status=scheduled + scheduled_at
in UTC), so it survives restarts by design: a single asyncio loop polls the
database and publishes anything that is due. Posts that became due while the
bot was down are published immediately on startup (catch-up).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot

from bot.core import states
from bot.db.repo import Repo
from bot.services.publisher import Publisher

logger = logging.getLogger(__name__)

POLL_INTERVAL = 20  # seconds


class Scheduler:
    def __init__(
        self,
        repo: Repo,
        publisher: Publisher,
        bot: Bot,
        *,
        poll_interval: float = POLL_INTERVAL,
    ) -> None:
        self.repo = repo
        self.publisher = publisher
        self.bot = bot
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="post-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        logger.info("scheduler started (poll every %ss)", self.poll_interval)
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 - keep the loop alive
                logger.exception("scheduler tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except TimeoutError:
                pass

    async def tick(self) -> int:
        """Publish every due scheduled post. Returns how many were published."""
        now = datetime.now(UTC)
        due = await self.repo.list_due_scheduled(now)
        published = 0
        for post in due:
            try:
                await self.publisher.publish(post)
                await self.repo.set_status(post.id, states.PUBLISHED)
                published += 1
                logger.info("scheduled post #%s published", post.id)
                await self._notify_author(post.created_by, post.id)
            except Exception:  # noqa: BLE001
                logger.exception("failed to publish scheduled post #%s", post.id)
        return published

    async def _notify_author(self, user_id: int, post_id: int) -> None:
        try:
            await self.bot.send_message(
                user_id, f"✅ Отложенный пост #{post_id} опубликован в канале."
            )
        except Exception:  # noqa: BLE001 - author may have blocked the bot
            logger.debug("could not notify author %s about post #%s", user_id, post_id)
