from bot.core.dburl import normalize_database_url


def test_empty_falls_back_to_sqlite():
    assert normalize_database_url(None) == "sqlite+aiosqlite:///bot.db"
    assert normalize_database_url("  ") == "sqlite+aiosqlite:///bot.db"


def test_postgres_scheme_upgraded():
    assert normalize_database_url("postgres://u:p@h:5432/db") == \
        "postgresql+asyncpg://u:p@h:5432/db"
    assert normalize_database_url("postgresql://u:p@h/db") == \
        "postgresql+asyncpg://u:p@h/db"


def test_sslmode_stripped_for_asyncpg():
    url = normalize_database_url("postgresql://u:p@h/db?sslmode=require&application_name=bot")
    assert "sslmode" not in url
    assert "application_name=bot" in url


def test_sqlite_scheme_upgraded():
    assert normalize_database_url("sqlite:///data.db") == "sqlite+aiosqlite:///data.db"
