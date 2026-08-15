"""Template management and post-from-template flow."""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.render import extract_placeholders, render_template_escaped
from bot.handlers import newpost
from bot.handlers.deps import Deps
from bot.handlers.filters import IsAdmin

router = Router(name="templates")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class TemplateFlow(StatesGroup):
    fill = State()          # filling placeholders one by one
    add_name = State()      # /addtemplate: waiting for name
    add_body = State()      # /addtemplate: waiting for body


# ---------------- list & view ----------------

@router.message(Command("templates"))
async def cmd_templates(message: Message, deps: Deps) -> None:
    templates = await deps.repo.list_templates()
    if not templates:
        await message.answer("Шаблонов нет. Добавить: /addtemplate")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 {t.name}", callback_data=f"tpl:{t.id}:use"),
         InlineKeyboardButton(text="👁", callback_data=f"tpl:{t.id}:view"),
         InlineKeyboardButton(text="🗑", callback_data=f"tpl:{t.id}:del")]
        for t in templates
    ])
    await message.answer(
        "📋 <b>Шаблоны магазина</b>\n"
        "Нажмите на название, чтобы создать пост из шаблона.\n"
        "👁 — посмотреть, 🗑 — удалить. Новый шаблон: /addtemplate",
        reply_markup=kb,
    )


@router.callback_query(F.data.regexp(r"^tpl:(\d+):view$"))
async def tpl_view(callback: CallbackQuery, deps: Deps) -> None:
    template_id = int(callback.data.split(":")[1])
    template = await deps.repo.get_template(template_id)
    await callback.answer()
    if template is None:
        await callback.message.answer("Шаблон не найден.")
        return
    placeholders = extract_placeholders(template.body)
    ph_line = ("\n\nПоля для заполнения: " + ", ".join(f"<code>{p}</code>" for p in placeholders)
               if placeholders else "")
    await callback.message.answer(
        f"📋 <b>{escape(template.name)}</b>\n\n<code>{escape(template.body)}</code>{ph_line}"
    )


@router.callback_query(F.data.regexp(r"^tpl:(\d+):del$"))
async def tpl_delete(callback: CallbackQuery, deps: Deps) -> None:
    template_id = int(callback.data.split(":")[1])
    deleted = await deps.repo.delete_template(template_id)
    await callback.answer("Удалён" if deleted else "Не найден")
    if deleted:
        await callback.message.answer("🗑 Шаблон удалён. Список: /templates")


# ---------------- use a template ----------------

@router.callback_query(F.data.regexp(r"^tpl:(\d+):use$"))
async def tpl_use(callback: CallbackQuery, state: FSMContext, deps: Deps) -> None:
    template_id = int(callback.data.split(":")[1])
    template = await deps.repo.get_template(template_id)
    await callback.answer()
    if template is None:
        await callback.message.answer("Шаблон не найден.")
        return

    await state.clear()
    placeholders = extract_placeholders(template.body)
    post = await deps.repo.create_post(callback.from_user.id)

    if not placeholders:
        await deps.repo.update_post_text(post.id, render_template_escaped(template.body))
        await callback.message.answer(
            f"📝 Пост #{post.id} создан из шаблона «{escape(template.name)}»."
        )
        await newpost.continue_with_text(callback.message, state, deps, post.id)
        return

    await state.set_state(TemplateFlow.fill)
    await state.update_data(
        post_id=post.id,
        body=template.body,
        placeholders=placeholders,
        values={},
        index=0,
    )
    await callback.message.answer(
        f"📝 Пост #{post.id} из шаблона «{escape(template.name)}».\n"
        f"Заполним {len(placeholders)} " +
        ("поле" if len(placeholders) == 1 else "поля(ей)") + ".\n\n" +
        _ask_line(placeholders[0], 1, len(placeholders))
    )


def _ask_line(name: str, num: int, total: int) -> str:
    return (f"({num}/{total}) Введите значение для <code>{{{name}}}</code>\n"
            "Отправьте <code>-</code>, чтобы пропустить поле.")


@router.message(TemplateFlow.fill, F.text)
async def tpl_fill_value(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    placeholders: list[str] = data["placeholders"]
    values: dict[str, str] = data["values"]
    index: int = data["index"]

    raw = message.text.strip()
    if raw != "-":
        values[placeholders[index]] = raw

    index += 1
    if index < len(placeholders):
        await state.update_data(values=values, index=index)
        await message.answer(_ask_line(placeholders[index], index + 1, len(placeholders)))
        return

    # Store the text HTML-escaped (same invariant as the /new flow): values are
    # admin-typed and may contain '<', '&' etc., which would otherwise break the
    # channel post sent with parse_mode=HTML.
    text = render_template_escaped(data["body"], values)
    post_id = int(data["post_id"])
    await deps.repo.update_post_text(post_id, text)
    await message.answer("✅ Текст поста готов:\n\n" + text)
    await newpost.continue_with_text(message, state, deps, post_id)


# ---------------- add / update a template ----------------

@router.message(Command("addtemplate"))
async def cmd_addtemplate(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TemplateFlow.add_name)
    await message.answer(
        "Название шаблона? (если такое уже есть — шаблон будет обновлён)\n"
        "Отмена — /cancel"
    )


@router.message(TemplateFlow.add_name, F.text, ~F.text.startswith("/"))
async def tpl_add_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) > 128:
        await message.answer("Слишком длинное название (максимум 128 символов).")
        return
    await state.update_data(name=name)
    await state.set_state(TemplateFlow.add_body)
    await message.answer(
        "Теперь пришлите <b>текст шаблона</b>.\n"
        "Переменные пишите в фигурных скобках: <code>{price}</code>, "
        "<code>{product_name}</code> — при создании поста бот попросит их заполнить."
    )


@router.message(TemplateFlow.add_body, F.text, ~F.text.startswith("/"))
async def tpl_add_body(message: Message, state: FSMContext, deps: Deps) -> None:
    data = await state.get_data()
    template = await deps.repo.upsert_template(data["name"], message.text)
    await state.clear()
    placeholders = extract_placeholders(template.body)
    ph_line = (" Поля: " + ", ".join(f"<code>{p}</code>" for p in placeholders)
               if placeholders else "")
    await message.answer(
        f"✅ Шаблон «{escape(template.name)}» сохранён.{ph_line}\n"
        "Использовать: /templates"
    )
