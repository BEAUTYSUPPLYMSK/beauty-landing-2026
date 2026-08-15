"""Start/help/id commands and the non-admin fallback."""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.handlers.deps import Deps
from bot.handlers.filters import IsAdmin

router = Router(name="common")

ADMIN_HELP = (
    "<b>Бот-администратор канала BEAUTYSUPPLYMSK</b>\n\n"
    "<b>Создание постов</b>\n"
    "/new — новый пост (текст → фото → кнопки → предпросмотр)\n"
    "/templates — создать пост из шаблона магазина\n\n"
    "<b>Управление</b>\n"
    "/posts — последние посты (черновики, отложенные, опубликованные)\n"
    "/scheduled — очередь отложенных постов\n"
    "/cancel — прервать текущее действие\n\n"
    "<b>Шаблоны</b>\n"
    "/templates — список шаблонов\n"
    "/addtemplate — добавить или обновить шаблон\n\n"
    "<b>Прочее</b>\n"
    "/id — показать ваш ID и ID этого чата\n"
    "/help — эта справка\n\n"
    "Отложенные посты публикуются автоматически и переживают перезапуск бота."
)

GUEST_TEXT = (
    "Привет! Это служебный бот магазина BEAUTYSUPPLYMSK.\n"
    "Управлять контентом могут только администраторы.\n\n"
    "Ваш ID: <code>{user_id}</code> — передайте его владельцу магазина, "
    "если вам нужен доступ."
)


@router.message(CommandStart(), IsAdmin())
async def cmd_start_admin(message: Message, deps: Deps) -> None:
    await message.answer(
        "👋 Добро пожаловать! Вы администратор.\n\n" + ADMIN_HELP
    )


@router.message(Command("help"), IsAdmin())
async def cmd_help(message: Message, deps: Deps) -> None:
    await message.answer(ADMIN_HELP)


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else "?"
    await message.answer(
        f"👤 Ваш ID: <code>{user_id}</code>\n"
        f"💬 ID этого чата: <code>{message.chat.id}</code>"
    )


@router.message(F.forward_from_chat, IsAdmin())
async def forwarded_from_channel(message: Message) -> None:
    chat = message.forward_from_chat
    title = escape(chat.title or "канал")
    await message.answer(
        f"📣 Это сообщение из «{title}».\n"
        f"ID канала: <code>{chat.id}</code>\n\n"
        "Используйте это значение как CHANNEL_ID."
    )


@router.message(CommandStart())
async def cmd_start_guest(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(GUEST_TEXT.format(user_id=user_id))


@router.message(Command("help"))
async def cmd_help_guest(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(GUEST_TEXT.format(user_id=user_id))
