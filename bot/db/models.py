"""SQLAlchemy models: posts, post photos, message mappings, templates."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bot.core import states


class Base(DeclarativeBase):
    pass


class Post(Base):
    """A channel post managed by the bot (draft/scheduled/published/deleted)."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), default=states.DRAFT, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    buttons_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # UTC time at which a scheduled post should be published.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    photos: Mapped[list[PostPhoto]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostPhoto.position",
        lazy="selectin",
    )
    messages: Mapped[list[PostMessage]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostMessage.position",
        lazy="selectin",
    )


class PostPhoto(Base):
    """Photo attached to a post (Telegram file_id), ordered."""

    __tablename__ = "post_photos"
    __table_args__ = (UniqueConstraint("post_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_id: Mapped[str] = mapped_column(String(512), nullable=False)

    post: Mapped[Post] = relationship(back_populates="photos")


class PostMessage(Base):
    """Mapping of a post to the actual message(s) in the channel.

    A text post or single-photo post maps to one message; an album maps to
    one row per album item (position 0 carries the caption).
    """

    __tablename__ = "post_messages"
    __table_args__ = (UniqueConstraint("post_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    post: Mapped[Post] = relationship(back_populates="messages")


class Template(Base):
    """Reusable post template with {placeholders}."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
