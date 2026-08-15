"""Publishing, editing and deleting posts in the target channel."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from bot.core import states
from bot.core.buttons import ButtonRows
from bot.db.models import Post
from bot.db.repo import Repo, buttons_from_json

logger = logging.getLogger(__name__)


def build_markup(rows: ButtonRows | None) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=b["text"], url=b["url"]) for b in row]
            for row in rows
        ]
    )


class Publisher:
    def __init__(self, bot: Bot, repo: Repo, channel_id: int | str) -> None:
        self.bot = bot
        self.repo = repo
        self.channel_id = channel_id

    # ---------------- publish ----------------

    async def publish(self, post: Post) -> list[int]:
        """Send the post to the channel; returns channel message ids.

        The caller is responsible for the state transition; this method only
        performs Telegram calls and records the message mapping.
        """
        markup = build_markup(buttons_from_json(post.buttons_json))
        photos = post.photos
        text = post.text or ""

        if not photos and not text.strip():
            raise ValueError("Пост пуст — добавьте текст или фото перед публикацией.")

        if not photos:
            message = await self.bot.send_message(
                self.channel_id, text, reply_markup=markup, disable_web_page_preview=False
            )
            message_ids = [message.message_id]
        elif len(photos) == 1:
            message = await self.bot.send_photo(
                self.channel_id, photos[0].file_id, caption=text or None, reply_markup=markup
            )
            message_ids = [message.message_id]
        else:
            media = [
                InputMediaPhoto(media=p.file_id, caption=(text or None) if i == 0 else None)
                for i, p in enumerate(photos)
            ]
            messages = await self.bot.send_media_group(self.channel_id, media)
            message_ids = [m.message_id for m in messages]
            if markup is not None:
                # Telegram does not support inline keyboards on albums; send
                # the buttons as a follow-up message replying to the album.
                extra = await self.bot.send_message(
                    self.channel_id,
                    "👇",
                    reply_markup=markup,
                    reply_to_message_id=message_ids[0],
                )
                message_ids.append(extra.message_id)

        chat_id = await self._resolve_chat_id(message_ids)
        await self.repo.save_channel_messages(post.id, chat_id, message_ids)
        return message_ids

    async def _resolve_chat_id(self, _message_ids: list[int]) -> int:
        if isinstance(self.channel_id, int):
            return self.channel_id
        chat = await self.bot.get_chat(self.channel_id)
        return chat.id

    # ---------------- edit ----------------

    async def edit_published(self, post: Post) -> None:
        """Push the current text/buttons of a published post to the channel.

        Works for plain text posts, single photos and albums (album caption
        lives on the first item). Photos themselves cannot be swapped after
        publication — Telegram only allows editing text/caption/markup.
        """
        if post.status != states.PUBLISHED or not post.messages:
            raise ValueError("post is not published")

        markup = build_markup(buttons_from_json(post.buttons_json))
        first = post.messages[0]
        text = post.text or ""

        if not post.photos:
            await self._ignore_not_modified(
                self.bot.edit_message_text(
                    text,
                    chat_id=first.chat_id,
                    message_id=first.message_id,
                    reply_markup=markup,
                )
            )
            return

        # Photo or album: edit the caption on the first message.
        album_button_holder = None
        if len(post.photos) > 1 and len(post.messages) > len(post.photos):
            album_button_holder = post.messages[-1]

        await self._ignore_not_modified(
            self.bot.edit_message_caption(
                chat_id=first.chat_id,
                message_id=first.message_id,
                caption=text or None,
                reply_markup=None if len(post.photos) > 1 else markup,
            )
        )
        if album_button_holder is not None:
            await self._ignore_not_modified(
                self.bot.edit_message_reply_markup(
                    chat_id=album_button_holder.chat_id,
                    message_id=album_button_holder.message_id,
                    reply_markup=markup,
                )
            )

    @staticmethod
    async def _ignore_not_modified(coro) -> None:
        try:
            await coro
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc):
                raise

    # ---------------- delete ----------------

    async def delete_published(self, post: Post) -> int:
        """Delete all channel messages of a post; returns how many were removed."""
        removed = 0
        for mapping in post.messages:
            try:
                await self.bot.delete_message(mapping.chat_id, mapping.message_id)
                removed += 1
            except TelegramBadRequest as exc:
                logger.warning(
                    "could not delete message %s/%s: %s",
                    mapping.chat_id, mapping.message_id, exc,
                )
        return removed

    # ---------------- preview ----------------

    async def send_preview(self, chat_id: int, post: Post) -> None:
        """Send the post to the admin's private chat exactly as it would appear."""
        markup = build_markup(buttons_from_json(post.buttons_json))
        photos = post.photos
        text = post.text or "(без текста)"

        if not photos:
            await self.bot.send_message(chat_id, text, reply_markup=markup)
        elif len(photos) == 1:
            await self.bot.send_photo(
                chat_id, photos[0].file_id, caption=post.text or None, reply_markup=markup
            )
        else:
            media = [
                InputMediaPhoto(media=p.file_id, caption=post.text if i == 0 else None)
                for i, p in enumerate(photos)
            ]
            await self.bot.send_media_group(chat_id, media)
            if markup is not None:
                await self.bot.send_message(chat_id, "👇 Кнопки под альбомом:", reply_markup=markup)
