"""Repository layer: all database access for posts and templates."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.core import states
from bot.core.buttons import ButtonRows
from bot.db.models import Post, PostMessage, PostPhoto, Template


class Repo:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    # ---------------- posts ----------------

    async def create_post(self, created_by: int) -> Post:
        async with self._sf() as session:
            post = Post(status=states.DRAFT, created_by=created_by, text="")
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post

    async def get_post(self, post_id: int) -> Post | None:
        async with self._sf() as session:
            return await session.get(Post, post_id)

    async def list_posts(self, status: str | None = None, limit: int = 20) -> list[Post]:
        async with self._sf() as session:
            stmt = select(Post).order_by(Post.id.desc()).limit(limit)
            if status is not None:
                stmt = stmt.where(Post.status == status)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_due_scheduled(self, now_utc: datetime) -> list[Post]:
        async with self._sf() as session:
            stmt = (
                select(Post)
                .where(Post.status == states.SCHEDULED, Post.scheduled_at <= now_utc)
                .order_by(Post.scheduled_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_post_text(self, post_id: int, text: str) -> None:
        async with self._sf() as session:
            post = await session.get(Post, post_id)
            if post is None:
                raise LookupError(f"post {post_id} not found")
            post.text = text
            await session.commit()

    async def update_post_buttons(self, post_id: int, rows: ButtonRows | None) -> None:
        async with self._sf() as session:
            post = await session.get(Post, post_id)
            if post is None:
                raise LookupError(f"post {post_id} not found")
            post.buttons_json = json.dumps(rows, ensure_ascii=False) if rows else None
            await session.commit()

    async def add_photo(self, post_id: int, file_id: str, max_photos: int = 10) -> int:
        """Append a photo; returns the new photo count. Raises ValueError if full."""
        async with self._sf() as session:
            post = await session.get(Post, post_id)
            if post is None:
                raise LookupError(f"post {post_id} not found")
            count = len(post.photos)
            if count >= max_photos:
                raise ValueError(f"максимум {max_photos} фото")
            session.add(PostPhoto(post_id=post_id, position=count, file_id=file_id))
            await session.commit()
            return count + 1

    async def clear_photos(self, post_id: int) -> None:
        async with self._sf() as session:
            await session.execute(delete(PostPhoto).where(PostPhoto.post_id == post_id))
            await session.commit()

    async def set_status(
        self,
        post_id: int,
        target: str,
        *,
        scheduled_at: datetime | None = None,
        published_at: datetime | None = None,
    ) -> Post:
        """Transition a post through the state machine and persist timestamps."""
        async with self._sf() as session:
            post = await session.get(Post, post_id)
            if post is None:
                raise LookupError(f"post {post_id} not found")
            post.status = states.transition(post.status, target)
            if target == states.SCHEDULED:
                post.scheduled_at = scheduled_at
            elif target == states.PUBLISHED:
                post.published_at = published_at or datetime.now(UTC)
                post.scheduled_at = None
            elif target == states.DRAFT:
                post.scheduled_at = None
            await session.commit()
            await session.refresh(post)
            return post

    async def save_channel_messages(
        self, post_id: int, chat_id: int, message_ids: list[int]
    ) -> None:
        async with self._sf() as session:
            await session.execute(delete(PostMessage).where(PostMessage.post_id == post_id))
            for pos, mid in enumerate(message_ids):
                session.add(
                    PostMessage(post_id=post_id, position=pos, chat_id=chat_id, message_id=mid)
                )
            await session.commit()

    async def delete_post_row(self, post_id: int) -> None:
        async with self._sf() as session:
            post = await session.get(Post, post_id)
            if post is not None:
                await session.delete(post)
                await session.commit()

    # ---------------- templates ----------------

    async def list_templates(self) -> list[Template]:
        async with self._sf() as session:
            result = await session.execute(select(Template).order_by(Template.id))
            return list(result.scalars().all())

    async def get_template(self, template_id: int) -> Template | None:
        async with self._sf() as session:
            return await session.get(Template, template_id)

    async def upsert_template(self, name: str, body: str) -> Template:
        async with self._sf() as session:
            result = await session.execute(select(Template).where(Template.name == name))
            template = result.scalar_one_or_none()
            if template is None:
                template = Template(name=name, body=body)
                session.add(template)
            else:
                template.body = body
            await session.commit()
            await session.refresh(template)
            return template

    async def delete_template(self, template_id: int) -> bool:
        async with self._sf() as session:
            template = await session.get(Template, template_id)
            if template is None:
                return False
            await session.delete(template)
            await session.commit()
            return True

    async def seed_templates(self, items: list[tuple[str, str]]) -> int:
        """Insert templates that do not exist yet (by name). Returns count added."""
        added = 0
        async with self._sf() as session:
            for name, body in items:
                result = await session.execute(select(Template).where(Template.name == name))
                if result.scalar_one_or_none() is None:
                    session.add(Template(name=name, body=body))
                    added += 1
            await session.commit()
        return added


def buttons_from_json(buttons_json: str | None) -> ButtonRows | None:
    if not buttons_json:
        return None
    rows = json.loads(buttons_json)
    return rows or None
