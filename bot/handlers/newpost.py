"""Post composer: /new wizard (text → photos → buttons → preview → action)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core import states as post_states
from bot.core.buttons import parse_buttons
from bot.core.whenparse import FORMAT_HINT, parse_when
from bot.handlers.deps import Deps
from bot.handlers.filters import IsAdmin

router = Router(name="newpost")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

MAX_PHOTOS = 10
# Telegram limits: 4096 chars for text messages, 1024 for photo captions.
MAX_TEXT = 4096
MAX_CAPTION = 1024


class Compose(StatesGroup):
    text = State()
    photos = State()
    buttons = State()
    action = State()
    schedule = State()


def _photos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Дальше", callback_data="compose:photos_done"),
        InlineKeyboardButton(text="🗑 Убрать все фото", callback_data="compose:photos_clear"),
    ]])


def _buttons_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Без кнопок", callback_data="compose:no_buttons"),
    ]])


def _action_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data="compose:publish"),
            InlineKeyboardButton(text="⏰ Запланировать", callback_data="compose:schedule"),
        ],
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data="compose:edit_text"),
            InlineKeyboardButton(text="🖼 Фото", callback_data="compose:edit_photos"),
            InlineKeyboardButton(text="🔗 Кнопки", callback_data="compose:edit_buttons"),
        ],
        [
            InlineKeyboardButton(text="💾 Оставить черновиком", callback_data="compose:keep_draft"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data="compose:discard"),
        ],
    ])


async def _post_id(state: FSMContext) -> int:
    data = await state.get_data()
    return int(data["post_id"])


# ---------------- entry ----------------

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("Действие отменено. Черновик (если был) сохранён — см. /posts.")


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext, deps: Deps) -> None:
    await state.clear()
    post = await deps.repo.create_post(message.from_user.id)
    await state.set_state(Compose.text)
    await state.update_data(post_id=post.id)
    await message.answer(
        f"📝 Новый пост #{post.id}.\n\n"
        "Шаг 1/3 — отправьте <b>текст поста</b>.\n"
        "Можно использовать <b>жирный</b>, <i>курсив</i> и эмодзи.\n\n"
        "Отмена — /cancel"
    )


# Entry point used by templates.py after placeholders are filled.
async def continue_with_text(
    message: Message, state: FSMContext, deps: Deps, post_id: int
) -> None:
    await state.set_state(Compose.photos)
    await state.update_data(post_id=post_id)
    await message.answer(
        "Шаг 2/3 — пришлите <b>фото</b> (до 10 штук, по одному или альбомом), "
        "либо нажмите «Дальше».",
        reply_markup=_photos_kb(),
    )


# ---------------- step 1: text ----------------

@router.message(Compose.text, F.text)
async def got_text(message: Message, state: FSMContext, deps: Deps) -> None:
    text = message.html_text or message.text or ""
    if len(text) > MAX_TEXT:
        await message.answer(f"Слишком длинно ({len(text)} символов, максимум {MAX_TEXT}).")
        return
    await deps.repo.update_post_text(await _post_id(state), text)
    await continue_with_text(message, state, deps, await _post_id(state))


@router.message(Compose.text)
async def got_not_text(message: Message) -> None:
    await message.answer("Сейчас жду именно текст поста. Фото будут на следующем шаге.")


# ---------------- step 2: photos ----------------

@router.message(Compose.photos, F.photo)
async def got_photo(message: Message, state: FSMContext, deps: Deps) -> None:
    post_id = await _post_id(state)
    try:
        count = await deps.repo.add_photo(post_id, message.photo[-1].file_id, MAX_PHOTOS)
    except ValueError:
        await message.answer(f"Достигнут лимит {MAX_PHOTOS} фото. Нажмите «Дальше».",
                             reply_markup=_photos_kb())
        return
    # For albums Telegram delivers photos as separate messages; keep it quiet
    # and confirm only with a compact counter.
    if message.media_group_id is None or count == 1:
        await message.answer(f"🖼 Фото {count}/{MAX_PHOTOS} добавлено.", reply_markup=_photos_kb())


@router.callback_query(Compose.photos, F.data == "compose:photos_clear")
async def photos_clear(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await deps.repo.clear_photos(await _post_id(state))
    await callback.answer("Фото удалены")
    await callback.message.answer("Все фото убраны. Пришлите новые или нажмите «Дальше».",
                                  reply_markup=_photos_kb())


@router.callback_query(Compose.photos, F.data == "compose:photos_done")
async def photos_done(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    post = await deps.repo.get_post(await _post_id(state))
    if post.photos and post.text and len(post.text) > MAX_CAPTION:
        await callback.answer()
        await callback.message.answer(
            f"⚠️ Для поста с фото текст ограничен {MAX_CAPTION} символами "
            f"(сейчас {len(post.text)}). Сократите текст: нажмите «✏️ Текст» "
            "на предпросмотре или уберите фото."
        )
    await state.set_state(Compose.buttons)
    await callback.answer()
    await callback.message.answer(
        "Шаг 3/3 — <b>кнопки-ссылки</b> (необязательно).\n\n"
        "Каждая строка — ряд кнопок, формат:\n"
        "<code>Текст | https://ссылка</code>\n"
        "Две кнопки в ряд: <code>Кнопка 1 | ссылка && Кнопка 2 | ссылка</code>\n\n"
        "Пример:\n<code>🛍 Каталог | https://t.me/BEAUTYSUPPLYMSK\n"
        "💬 Написать нам | https://wa.me/79990000000</code>",
        reply_markup=_buttons_kb(),
    )


@router.message(Compose.photos)
async def photos_wrong_input(message: Message) -> None:
    await message.answer("Пришлите фото или нажмите «Дальше».", reply_markup=_photos_kb())


# ---------------- step 3: buttons ----------------

@router.callback_query(Compose.buttons, F.data == "compose:no_buttons")
async def no_buttons(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await deps.repo.update_post_buttons(await _post_id(state), None)
    await callback.answer()
    await _show_preview(callback.message, state, deps)


@router.message(Compose.buttons, F.text)
async def got_buttons(message: Message, state: FSMContext, deps: Deps) -> None:
    try:
        rows = parse_buttons(message.text)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}\n\nПопробуйте ещё раз или нажмите «Без кнопок».",
                             reply_markup=_buttons_kb())
        return
    await deps.repo.update_post_buttons(await _post_id(state), rows)
    await _show_preview(message, state, deps)


# ---------------- preview & actions ----------------

async def _show_preview(message: Message, state: FSMContext, deps: Deps) -> None:
    post = await deps.repo.get_post(await _post_id(state))
    await state.set_state(Compose.action)
    await message.answer("👀 <b>Предпросмотр</b> — так пост будет выглядеть в канале:")
    await deps.publisher.send_preview(message.chat.id, post)
    await message.answer("Что делаем с постом?", reply_markup=_action_kb())


@router.callback_query(Compose.action, F.data == "compose:publish")
async def action_publish(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    post = await deps.repo.get_post(await _post_id(state))
    await callback.answer()
    try:
        await deps.publisher.publish(post)
    except Exception as exc:  # noqa: BLE001
        await callback.message.answer(
            f"❌ Не удалось опубликовать: <code>{exc}</code>\n"
            "Проверьте, что бот добавлен в канал как администратор."
        )
        return
    await deps.repo.set_status(post.id, post_states.PUBLISHED)
    await state.clear()
    await callback.message.answer(f"✅ Пост #{post.id} опубликован в канале!")


@router.callback_query(Compose.action, F.data == "compose:schedule")
async def action_schedule(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Compose.schedule)
    await callback.answer()
    await callback.message.answer(
        "⏰ Когда опубликовать?\n\n" + FORMAT_HINT +
        "\n\nВремя — по часовому поясу магазина."
    )


@router.message(Compose.schedule, F.text)
async def got_schedule_time(message: Message, state: FSMContext, deps: Deps) -> None:
    tz = deps.config.tz
    try:
        when = parse_when(message.text, now=datetime.now(UTC), tz=tz)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}\n\n{FORMAT_HINT}")
        return
    post_id = await _post_id(state)
    await deps.repo.set_status(post_id, post_states.SCHEDULED,
                               scheduled_at=when.astimezone(UTC))
    await state.clear()
    await message.answer(
        f"⏰ Пост #{post_id} запланирован на "
        f"<b>{when.strftime('%d.%m.%Y %H:%M')}</b> ({deps.config.timezone}).\n"
        "Он будет опубликован автоматически, даже если бот перезапустится.\n"
        "Очередь: /scheduled"
    )


@router.callback_query(Compose.action, F.data == "compose:edit_text")
async def action_edit_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Compose.text)
    await callback.answer()
    await callback.message.answer("Пришлите новый текст поста:")


@router.callback_query(Compose.action, F.data == "compose:edit_photos")
async def action_edit_photos(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    await deps.repo.clear_photos(await _post_id(state))
    await state.set_state(Compose.photos)
    await callback.answer()
    await callback.message.answer(
        "Старые фото убраны. Пришлите новые (до 10) или нажмите «Дальше».",
        reply_markup=_photos_kb(),
    )


@router.callback_query(Compose.action, F.data == "compose:edit_buttons")
async def action_edit_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Compose.buttons)
    await callback.answer()
    await callback.message.answer(
        "Пришлите новые кнопки (формат: <code>Текст | ссылка</code>) "
        "или нажмите «Без кнопок».",
        reply_markup=_buttons_kb(),
    )


@router.callback_query(Compose.action, F.data == "compose:keep_draft")
async def action_keep_draft(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        f"💾 Пост #{data['post_id']} сохранён как черновик. Вернуться к нему: /posts"
    )


@router.callback_query(Compose.action, F.data == "compose:discard")
async def action_discard(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    post_id = await _post_id(state)
    await deps.repo.delete_post_row(post_id)
    await state.clear()
    await callback.answer("Удалено")
    await callback.message.answer(f"🗑 Черновик #{post_id} удалён.")
