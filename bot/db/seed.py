"""Default store templates for BEAUTYSUPPLYMSK, seeded on first start.

Placeholders in {curly_braces} are filled in by the admin when creating a
post from a template; any left unfilled stay visible so they can be edited
manually before publishing.
"""

from __future__ import annotations

DEFAULT_TEMPLATES: list[tuple[str, str]] = [
    (
        "Новинка",
        "✨ НОВИНКА В BEAUTYSUPPLYMSK ✨\n\n"
        "{product_name}\n\n"
        "{description}\n\n"
        "💰 Цена: {price} ₽\n"
        "📦 В наличии в Москве, отправка по всей России\n\n"
        "📲 Заказ в директ или по кнопке ниже 👇",
    ),
    (
        "Акция",
        "🔥 АКЦИЯ 🔥\n\n"
        "{offer}\n\n"
        "⏳ Только до {deadline}!\n\n"
        "Количество ограничено — успейте забрать своё 💅\n"
        "📲 Пишите в директ или жмите кнопку ниже 👇",
    ),
    (
        "Поступление товара",
        "📦 ПОСТУПЛЕНИЕ ТОВАРА\n\n"
        "Сегодня на складе пополнение:\n\n"
        "{items}\n\n"
        "Всё уже в наличии — разбирают быстро!\n"
        "📲 Бронируйте в директ 👇",
    ),
    (
        "Товар дня",
        "⭐ ТОВАР ДНЯ ⭐\n\n"
        "{product_name} — всего {price} ₽ вместо {old_price} ₽!\n\n"
        "{description}\n\n"
        "Предложение действует только сегодня 🕛",
    ),
    (
        "Отзыв клиента",
        "💬 ОТЗЫВ НАШЕГО КЛИЕНТА\n\n"
        "«{review}»\n\n"
        "— {client_name}\n\n"
        "Спасибо, что выбираете BEAUTYSUPPLYMSK 💜\n"
        "Свой отзыв можно оставить в комментариях или в директ.",
    ),
    (
        "Режим работы",
        "🕐 РЕЖИМ РАБОТЫ\n\n"
        "{schedule}\n\n"
        "📍 Адрес: {address}\n"
        "🚇 {metro}\n\n"
        "Ждём вас! Онлайн-заказы принимаем круглосуточно 💌",
    ),
    (
        "Как заказать",
        "🛍 КАК СДЕЛАТЬ ЗАКАЗ\n\n"
        "1️⃣ Выберите товары в нашем канале или каталоге\n"
        "2️⃣ Напишите нам в директ: {contact}\n"
        "3️⃣ Подтвердите заказ и способ получения\n"
        "4️⃣ Самовывоз в Москве или доставка по России\n\n"
        "💳 Оплата: перевод / карта / при получении\n"
        "❓ Остались вопросы — пишите, мы на связи!",
    ),
]
