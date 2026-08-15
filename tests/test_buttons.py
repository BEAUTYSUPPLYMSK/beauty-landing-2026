import pytest

from bot.core.buttons import buttons_to_text, parse_buttons


def test_single_button():
    rows = parse_buttons("Каталог | https://example.com")
    assert rows == [[{"text": "Каталог", "url": "https://example.com"}]]


def test_two_rows_two_columns():
    spec = "A | https://a.com && B | https://b.com\nC | https://c.com"
    rows = parse_buttons(spec)
    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert rows[1][0]["text"] == "C"


def test_roundtrip():
    spec = "A | https://a.com && B | https://b.com\nC | tg://resolve?domain=x"
    assert buttons_to_text(parse_buttons(spec)) == spec


@pytest.mark.parametrize("bad", ["", "no separator", "X | ftp://nope", " | https://a.com"])
def test_invalid_specs(bad):
    with pytest.raises(ValueError):
        parse_buttons(bad)
