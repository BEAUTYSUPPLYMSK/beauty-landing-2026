"""Parsing and validation of inline URL buttons.

Admin input format (one row per line, buttons in a row separated by `&&`):

    Каталог | https://example.com/catalog
    WhatsApp | https://wa.me/79990000000 && Телефон | https://t.me/beautysupplymsk
"""

from __future__ import annotations

_ALLOWED_SCHEMES = ("http://", "https://", "tg://")

ButtonRows = list[list[dict[str, str]]]


def parse_buttons(text: str) -> ButtonRows:
    """Parse the admin-supplied button spec into rows of {text, url} dicts.

    Raises ValueError with a human-readable (Russian) message on bad input.
    """
    rows: ButtonRows = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        row: list[dict[str, str]] = []
        for raw_button in line.split("&&"):
            part = raw_button.strip()
            if not part:
                continue
            if "|" not in part:
                raise ValueError(
                    f"Строка {line_no}: не найден разделитель «|». "
                    "Формат: Текст кнопки | https://ссылка"
                )
            label, _, url = part.partition("|")
            label = label.strip()
            url = url.strip()
            if not label:
                raise ValueError(f"Строка {line_no}: пустой текст кнопки.")
            if not url.lower().startswith(_ALLOWED_SCHEMES):
                raise ValueError(
                    f"Строка {line_no}: ссылка должна начинаться с "
                    "http://, https:// или tg:// — получено: " + (url or "(пусто)")
                )
            row.append({"text": label, "url": url})
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("Не найдено ни одной кнопки. Формат: Текст | https://ссылка")
    return rows


def buttons_to_text(rows: ButtonRows) -> str:
    """Inverse of parse_buttons — used to prefill the edit prompt."""
    return "\n".join(
        " && ".join(f"{b['text']} | {b['url']}" for b in row) for row in rows
    )
