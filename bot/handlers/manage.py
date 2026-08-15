"""Managing existing posts: list, open, publish, reschedule, edit, delete."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core import states as post_states
from bot.core.buttons import buttons_to_text, parse_buttons
from bot.core.whenparse import FORMAT_HINT, parse_when
from bot.db.models import Post
from bot.db.repo import Repo, buttons_from_json
from bot.handlers.deps import Deps
from bot.handlers.filters import IsAdmin

router = Router(name="manage")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

STATUS_ICONS = {
    post_states.DRAFT: "📝",
    post_states.SCHEDULED: "⏰",
    post_states.PUBLISHED: "✅",
    post_states.DELETED: "🗑",
}
STATUS_NAMES = {
    post_states.DRAFT: "черновик",
    post_states.SCHEDULED: "запланирован",
    post_states.PUBLISHED: "опубликован",
    post_states.DELETED: "удалён",
}


class ManageEdit(StatesGroup):
    text = State()
    buttons = State()
    reschedule = State()


def _summary(post: Post, tz) -> str:
    icon = STATUS_ICONS.get(post.status, "❓")
    name = STATUS_NAMES.get(post.status, post.status)
    snippet = (post.text or "(без текста)").replace("\n", " ")
    if len(snippet) > 40:
        snippet = snippet[:40] + "…"
    extra = ""
    if post.status == post_states.SCHEDULED and post.scheduled_at:
        local = _as_utc(post.scheduled_at).astimezone(tz)
        extra = f" → {local.strftime('%d.%m %H:%M')}"
    return f"{icon} #{post.id} [{name}{extra}] {escape(snippet)}"


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _post_kb(post: Post) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pid = post.id
    if post.status == post_states.DRAFT:
        rows.append([
            InlineKeyboardButton(text="🚀 Опубликовать", callback_data=f"post:{pid}:publish"),
            InlineKeyboardButton(text="⏰ Запланировать", callback_data=f"post:{pid}:schedule"),
        ])
        rows.append([
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"post:{pid}:edit_text"),
            InlineKeyboardButton(text="🔗 Кнопки", callback_data=f"post:{pid}:edit_buttons"),
        ])
        rows.append([
            InlineKeyboardButton(text="🗑 Удалить черновик", callback_data=f"post:{pid}:discard"),
        ])
    elif post.status == post_states.SCHEDULED:
        rows.append([
            InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"post:{pid}:publish"),
            InlineKeyboardButton(text="⏰ Перенести", callback_data=f"post:{pid}:schedule"),
        ])
        rows.append([
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"post:{pid}:edit_text"),
            InlineKeyboardButton(text="🔗 Кнопки", callback_data=f"post:{pid}:edit_buttons"),
        ])
        rows.append([
            InlineKeyboardButton(text="↩️ В черновики", callback_data=f"post:{pid}:unschedule"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"post:{pid}:discard"),
        ])
    elif post.status == post_states.PUBLISHED:
        rows.append([
            InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"post:{pid}:edit_text"),
            InlineKeyboardButton(text="🔗 Изменить кнопки", callback_data=f"post:{pid}:edit_buttons"),
        ])
        rows.append([
            InlineKeyboardButton(text="🗑 Удалить из канала", callback_data=f"post:{pid}:delete"),
        ])
    rows.append([InlineKeyboardButton(text="👀 Предпросмотр", callback_data=f"post:{pid}:preview")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_kb(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Да, удалить из канала",
                             callback_data=f"post:{post_id}:delete_yes"),
        InlineKeyboardButton(text="Отмена", callback_data=f"post:{post_id}:open"),
    ]])


async def _open_post(message: Message, repo: Repo, post_id: int, tz) -> None:
    post = await repo.get_post(post_id)
    if post is None:
        await message.answer("Пост не найден.")
        return
    lines = [_summary(post, tz)]
    if post.photos:
        lines.append(f"🖼 Фото: {len(post.photos)}")
    if post.buttons_json:
        lines.append("🔗 Кнопки: есть")
    await message.answer("\n".join(lines), reply_markup=_post_kb(post))


# ---------------- lists ----------------

@router.message(Command("posts"))
async def cmd_posts(message: Message, deps: Deps) -> None:
    posts = [p for p in await deps.repo.list_posts(limit=15)
             if p.status != post_states.DELETED]
    if not posts:
        await message.answer("Постов пока нет. Создайте первый: /new")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_summary(p, deps.config.tz)[:60],
                              callback_data=f"post:{p.id}:open")]
        for p in posts
    ])
    await message.answer("📚 Последние посты — нажмите, чтобы открыть:", reply_markup=kb)


@router.message(Command("scheduled"))
async def cmd_scheduled(message: Message, deps: Deps) -> None:
    posts = await deps.repo.list_posts(status=post_states.SCHEDULED, limit=25)
    if not posts:
        await message.answer("Очередь пуста. Запланировать пост: /new → «Запланировать».")
        return
    posts.sort(key=lambda p: _as_utc(p.scheduled_at or datetime.max.replace(tzinfo=UTC)))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_summary(p, deps.config.tz)[:60],
                              callback_data=f"post:{p.id}:open")]
        for p in posts
    ])
    await message.answer("⏰ Отложенные посты:", reply_markup=kb)


# ---------------- callbacks ----------------

@router.callback_query(F.data.regexp(r"^post:(\d+):(\w+)$"))
async def post_action(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    _, pid_str, action = callback.data.split(":")
    post_id = int(pid_str)
    post = await deps.repo.get_post(post_id)
    if post is None:
        await callback.answer("Пост не найден", show_alert=True)
        return
    tz = deps.config.tz

    if action == "open":
        await callback.answer()
        await _open_post(callback.message, deps.repo, post_id, tz)

    elif action == "preview":
        await callback.answer()
        await deps.publisher.send_preview(callback.message.chat.id, post)

    elif action == "publish":
        if post.status not in (post_states.DRAFT, post_states.SCHEDULED):
            await callback.answer("Пост уже опубликован", show_alert=True)
            return
        await callback.answer()
        try:
            await deps.publisher.publish(post)
        except Exception as exc:  # noqa: BLE001
            await callback.message.answer(
                f"❌ Не удалось опубликовать: <code>{escape(str(exc))}</code>\n"
                "Проверьте, что бот — администратор канала."
            )
            return
        await deps.repo.set_status(post_id, post_states.PUBLISHED)
        await callback.message.answer(f"✅ Пост #{post_id} опубликован!")

    elif action == "schedule":
        await state.set_state(ManageEdit.reschedule)
        await state.update_data(post_id=post_id)
        await callback.answer()
        await callback.message.answer("⏰ Когда опубликовать?\n\n" + FORMAT_HINT)

    elif action == "unschedule":
        if post.status != post_states.SCHEDULED:
            await callback.answer("Пост не запланирован", show_alert=True)
            return
        await deps.repo.set_status(post_id, post_states.DRAFT)
        await callback.answer("Возвращён в черновики")
        await _open_post(callback.message, deps.repo, post_id, tz)

    elif action == "edit_text":
        await state.set_state(ManageEdit.text)
        await state.update_data(post_id=post_id)
        await callback.answer()
        note = ("\n\n⚠️ Пост уже в канале — текст обновится прямо там."
                if post.status == post_states.PUBLISHED else "")
        await callback.message.answer("Пришлите новый текст поста:" + note)

    elif action == "edit_buttons":
        await state.set_state(ManageEdit.buttons)
        await state.update_data(post_id=post_id)
        await callback.answer()
        current = buttons_from_json(post.buttons_json)
        current_text = (
            "\n\nТекущие кнопки:\n<code>" + escape(buttons_to_text(current)) + "</code>"
            if current else ""
        )
        await callback.message.answer(
            "Пришлите кнопки (формат: <code>Текст | ссылка</code>), "
            "или отправьте <code>-</code>, чтобы убрать кнопки." + current_text
        )

    elif action == "discard":
        if post.status == post_states.PUBLISHED:
            await callback.answer("Опубликованный пост удаляйте через «Удалить из канала»",
                                  show_alert=True)
            return
        await deps.repo.delete_post_row(post_id)
        await callback.answer("Удалено")
        await callback.message.answer(f"🗑 Пост #{post_id} удалён.")

    elif action == "delete":
        if post.status != post_states.PUBLISHED:
            await callback.answer("Пост не опубликован", show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(
            f"Удалить пост #{post_id} из канала? Это действие необратимо.",
            reply_markup=_confirm_delete_kb(post_id),
        )

    elif action == "delete_yes":
        if post.status != post_states.PUBLISHED:
            await callback.answer("Пост не опубликован", show_alert=True)
            return
        await callback.answer()
        removed = await deps.publisher.delete_published(post)
        await deps.repo.set_status(post_id, post_states.DELETED)
        await callback.message.answer(
            f"🗑 Пост #{post_id} удалён из канала (сообщений удалено: {removed})."
        )

    else:
        await callback.answer("Неизвестное действие", show_alert=True)


# ---------------- FSM: edits ----------------

@router.message(ManageEdit.text, F.text)
async def manage_new_text(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    post_id = int(data["post_id"])
    text = message.html_text or message.text or ""
    post = await deps.repo.get_post(post_id)
    if post is None:
        await state.clear()
        await message.answer("Пост не найден.")
        return
    if post.photos and len(text) > 1024:
        await message.answer(f"Для поста с фото максимум 1024 символа (сейчас {len(text)}).")
        return
    if len(text) > 4096:
        await message.answer(f"Максимум 4096 символов (сейчас {len(text)}).")
        return

    await deps.repo.update_post_text(post_id, text)
    post = await deps.repo.get_post(post_id)
    await state.clear()

    if post.status == post_states.PUBLISHED:
        try:
            await deps.publisher.edit_published(post)
        except Exception as exc:  # noqa: BLE001
            await message.answer(f"⚠️ Текст сохранён, но обновить пост в канале не удалось: "
                                 f"<code>{escape(str(exc))}</code>")
            return
        await message.answer(f"✏️ Пост #{post_id} обновлён в канале.")
    else:
        await message.answer(f"✏️ Текст поста #{post_id} обновлён.")
        await _open_post(message, deps.repo, post_id, deps.config.tz)


@router.message(ManageEdit.buttons, F.text)
async def manage_new_buttons(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    post_id = int(data["post_id"])
    raw = message.text.strip()
    if raw == "-":
        rows = None
    else:
        try:
            rows = parse_buttons(raw)
        except ValueError as exc:
            await message.answer(f"⚠️ {exc}")
            return
    await deps.repo.update_post_buttons(post_id, rows)
    post = await deps.repo.get_post(post_id)
    await state.clear()

    if post is not None and post.status == post_states.PUBLISHED:
        try:
            await deps.publisher.edit_published(post)
        except Exception as exc:  # noqa: BLE001
            await message.answer(f"⚠️ Кнопки сохранены, но обновить пост в канале не удалось: "
                                 f"<code>{escape(str(exc))}</code>")
            return
        await message.answer(f"🔗 Кнопки поста #{post_id} обновлены в канале.")
    else:
        await message.answer(f"🔗 Кнопки поста #{post_id} обновлены.")
        await _open_post(message, deps.repo, post_id, deps.config.tz)


@router.message(ManageEdit.reschedule, F.text)
async def manage_reschedule(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    post_id = int(data["post_id"])
    try:
        when = parse_when(message.text, now=datetime.now(UTC), tz=deps.config.tz)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}\n\n{FORMAT_HINT}")
        return
    await deps.repo.set_status(post_id, post_states.SCHEDULED,
                               scheduled_at=when.astimezone(UTC))
    await state.clear()
    await message.answer(
        f"⏰ Пост #{post_id} запланирован на <b>{when.strftime('%d.%m.%Y %H:%M')}</b> "
        f"({deps.config.timezone}). Очередь: /scheduled"
    )
