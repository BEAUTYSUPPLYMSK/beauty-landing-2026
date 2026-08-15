from bot.core.render import extract_placeholders, render_template


def test_render_substitutes_known_placeholders():
    assert render_template("Цена: {price} ₽", {"price": 990}) == "Цена: 990 ₽"


def test_render_keeps_unknown_placeholders():
    body = "{product_name} за {price} ₽"
    assert render_template(body, {"price": 500}) == "{product_name} за 500 ₽"


def test_render_no_placeholders():
    assert render_template("Просто текст", {}) == "Просто текст"


def test_render_repeated_placeholder():
    assert render_template("{x} и {x}", {"x": "a"}) == "a и a"


def test_extract_placeholders_ordered_unique():
    body = "{b} {a} {b} {c}"
    assert extract_placeholders(body) == ["b", "a", "c"]


def test_extract_placeholders_empty():
    assert extract_placeholders("нет полей") == []
