from bot.core.render import extract_placeholders, render_template, render_template_escaped


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


def test_render_escaped_sanitizes_values():
    out = render_template_escaped("{name} за {price} ₽", {"name": "<b>крем</b>", "price": "100&500"})
    # Escaped so publishing with parse_mode=HTML is safe and shows literal text.
    assert out == "&lt;b&gt;крем&lt;/b&gt; за 100&amp;500 ₽"


def test_render_escaped_keeps_unknown_placeholders():
    out = render_template_escaped("{missing} & {known}", {"known": "да"})
    assert out == "{missing} &amp; да"


def test_render_escaped_no_placeholders():
    assert render_template_escaped("Просто текст") == "Просто текст"
