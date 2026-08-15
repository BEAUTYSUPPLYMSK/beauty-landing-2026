"""Scheduler logic tests with a fake publisher (no Telegram calls)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from bot.core import states
from bot.db.repo import Repo
from bot.db.session import init_db, make_engine, make_session_factory
from bot.services.scheduler import Scheduler


class FakePublisher:
    def __init__(self, fail_ids=()):
        self.published = []
        self.fail_ids = set(fail_ids)

    async def publish(self, post):
        if post.id in self.fail_ids:
            raise RuntimeError("boom")
        self.published.append(post.id)
        return [1]


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


@pytest.fixture()
def env():
    loop = asyncio.new_event_loop()

    async def _make():
        engine = make_engine("sqlite+aiosqlite://")
        await init_db(engine)
        return engine, Repo(make_session_factory(engine))

    engine, repo = loop.run_until_complete(_make())
    yield loop, repo
    loop.run_until_complete(engine.dispose())
    loop.close()


def test_tick_publishes_due_posts_and_notifies(env):
    loop, repo = env
    publisher = FakePublisher()
    bot = FakeBot()
    scheduler = Scheduler(repo, publisher, bot)

    now = datetime.now(UTC)

    async def scenario():
        due = await repo.create_post(created_by=777)
        future = await repo.create_post(created_by=777)
        await repo.set_status(due.id, states.SCHEDULED, scheduled_at=now - timedelta(minutes=1))
        await repo.set_status(future.id, states.SCHEDULED, scheduled_at=now + timedelta(hours=1))

        published = await scheduler.tick()
        assert published == 1
        assert publisher.published == [due.id]

        refreshed = await repo.get_post(due.id)
        assert refreshed.status == states.PUBLISHED
        still_scheduled = await repo.get_post(future.id)
        assert still_scheduled.status == states.SCHEDULED
        assert bot.messages and bot.messages[0][0] == 777

        # second tick: nothing left to do (restart-safe: state is in the DB)
        assert await scheduler.tick() == 0

    loop.run_until_complete(scenario())


def test_tick_survives_publish_failure(env):
    loop, repo = env

    async def scenario():
        bad = await repo.create_post(created_by=1)
        good = await repo.create_post(created_by=1)
        now = datetime.now(UTC)
        await repo.set_status(bad.id, states.SCHEDULED, scheduled_at=now - timedelta(minutes=2))
        await repo.set_status(good.id, states.SCHEDULED, scheduled_at=now - timedelta(minutes=1))

        publisher = FakePublisher(fail_ids={bad.id})
        scheduler = Scheduler(repo, publisher, FakeBot())
        published = await scheduler.tick()
        assert published == 1
        assert publisher.published == [good.id]
        # the failed post stays scheduled and will be retried next tick
        assert (await repo.get_post(bad.id)).status == states.SCHEDULED

    loop.run_until_complete(scenario())
