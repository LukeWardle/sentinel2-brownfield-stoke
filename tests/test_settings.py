"""
test_settings.py - Unit tests for the centralised settings layer (P0-3).
"""

import pytest

from src.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """get_settings is lru_cached; clear around every test so env
    monkeypatching takes effect and cannot leak between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql://u:p@localhost:5432/db"


def test_settings_reads_copernicus_credentials_from_env(monkeypatch):
    monkeypatch.setenv("COPERNICUS_USERNAME", "user@example.com")
    monkeypatch.setenv("COPERNICUS_PASSWORD", "hunter2")
    settings = Settings(_env_file=None)
    assert settings.copernicus_username == "user@example.com"
    assert settings.copernicus_password == "hunter2"


def test_settings_fields_default_to_none_when_absent(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("COPERNICUS_USERNAME", raising=False)
    monkeypatch.delenv("COPERNICUS_PASSWORD", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.copernicus_username is None
    assert settings.copernicus_password is None


def test_settings_ignores_unknown_env_vars(monkeypatch):
    monkeypatch.setenv("SOME_UNRELATED_VAR", "value")
    settings = Settings(_env_file=None)  # extra="ignore" — must not raise
    assert isinstance(settings, Settings)


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://first@h/db")
    first = get_settings()
    monkeypatch.setenv("DATABASE_URL", "postgresql://second@h/db")
    second = get_settings()
    assert first is second  # cached — env change invisible until cache_clear

    get_settings.cache_clear()
    third = get_settings()
    assert third.database_url == "postgresql://second@h/db"


def test_get_db_connection_error_message_when_url_missing(monkeypatch):
    """The settings refactor must preserve get_db_connection's contract:
    a clear ValueError when DATABASE_URL is absent."""
    from src.database_query import get_db_connection

    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    # Force settings to skip any real .env file so the test is hermetic
    monkeypatch.setattr(
        "src.database_query.get_settings", lambda: Settings(_env_file=None)
    )
    with pytest.raises(ValueError, match="DATABASE_URL"):
        get_db_connection()
