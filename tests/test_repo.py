"""Integration tests of the repository + state machine over in-memory SQLite."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from bot.core import states
from bot.db.repo import Repo, buttons_from_json
from bot.db.session import init_db, make_engine, make_session_factory


@pytest.fixture()
def repo():
    async def _make():
        engine = make_engine("sqlite+aiosqlite://")
        await init_db(engine)
        return engine, Repo(make_session_factory(engine))

    loop = asyncio.new_event_loop()
    engine, repo = loop.run_until_complete(_make())
    yield loop, repo
    loop.run_until_complete(engine.dispose())
    loop.close()


def run(fixture, coro):
    loop, _ = fixture
    return loop.run_until_complete(coro)


def test_post_lifecycle_draft_schedule_publish(repo):
    _, r = repo
    post = run(repo, r.create_post(created_by=1))
    assert post.status == states.DRAFT

    run(repo, r.update_post_text(post.id, "hello"))
    when = datetime.now(UTC) + timedelta(hours=1)
    post = run(repo, r.set_status(post.id, states.SCHEDULED, scheduled_at=when))
    assert post.status == states.SCHEDULED
    assert post.scheduled_at is not None

    post = run(repo, r.set_status(post.id, states.PUBLISHED))
    assert post.status == states.PUBLISHED
    assert post.scheduled_at is None
    assert post.published_at is not None

    # published -> scheduled is illegal
    with pytest.raises(ValueError):
        run(repo, r.set_status(post.id, states.SCHEDULED, scheduled_at=when))


def test_due_scheduled_query(repo):
    _, r = repo
    past = run(repo, r.create_post(created_by=1))
    future = run(repo, r.create_post(created_by=1))
    now = datetime.now(UTC)
    run(repo, r.set_status(past.id, states.SCHEDULED, scheduled_at=now - timedelta(minutes=5)))
    run(repo, r.set_status(future.id, states.SCHEDULED, scheduled_at=now + timedelta(hours=5)))

    due = run(repo, r.list_due_scheduled(now))
    assert [p.id for p in due] == [past.id]


def test_photos_limit_and_order(repo):
    _, r = repo
    post = run(repo, r.create_post(created_by=1))
    for i in range(3):
        run(repo, r.add_photo(post.id, f"file{i}", max_photos=3))
    with pytest.raises(ValueError):
        run(repo, r.add_photo(post.id, "overflow", max_photos=3))
    post = run(repo, r.get_post(post.id))
    assert [p.file_id for p in post.photos] == ["file0", "file1", "file2"]

    run(repo, r.clear_photos(post.id))
    post = run(repo, r.get_post(post.id))
    assert post.photos == []


def test_buttons_roundtrip(repo):
    _, r = repo
    post = run(repo, r.create_post(created_by=1))
    rows = [[{"text": "A", "url": "https://a.com"}]]
    run(repo, r.update_post_buttons(post.id, rows))
    post = run(repo, r.get_post(post.id))
    assert buttons_from_json(post.buttons_json) == rows
    run(repo, r.update_post_buttons(post.id, None))
    post = run(repo, r.get_post(post.id))
    assert buttons_from_json(post.buttons_json) is None


def test_channel_message_mapping(repo):
    _, r = repo
    post = run(repo, r.create_post(created_by=1))
    run(repo, r.save_channel_messages(post.id, -100123, [11, 12, 13]))
    post = run(repo, r.get_post(post.id))
    assert [m.message_id for m in post.messages] == [11, 12, 13]
    assert all(m.chat_id == -100123 for m in post.messages)


def test_template_seed_is_idempotent(repo):
    _, r = repo
    items = [("Акция", "тело {x}"), ("Новинка", "тело")]
    assert run(repo, r.seed_templates(items)) == 2
    assert run(repo, r.seed_templates(items)) == 0
    templates = run(repo, r.list_templates())
    assert {t.name for t in templates} == {"Акция", "Новинка"}


def test_template_upsert_and_delete(repo):
    _, r = repo
    t = run(repo, r.upsert_template("Тест", "v1"))
    t2 = run(repo, r.upsert_template("Тест", "v2"))
    assert t.id == t2.id and t2.body == "v2"
    assert run(repo, r.delete_template(t.id)) is True
    assert run(repo, r.delete_template(t.id)) is False
