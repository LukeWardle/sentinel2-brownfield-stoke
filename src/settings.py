"""
settings.py - Centralised, validated application settings (P0-3).
=================================================================
Single source of truth for configuration. Every module that previously
called os.getenv / load_dotenv directly now imports get_settings() from
here, so environment handling happens exactly once and the connection
contract is documented in one place.

Values are read from the process environment first, then from a .env file
in the project root. Fields are optional at load time so that pure-unit
test runs without a database or Copernicus account still import cleanly;
validation happens at the point of use (get_db_connection raises if
DATABASE_URL is absent, authenticate raises if credentials are absent),
preserving the exact error behaviour callers already rely on.

DATABASE_URL is the sole database connection contract (a libpq URI); the
discrete DB_* variables referenced by older docs are not read.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None
    copernicus_username: str | None = None
    copernicus_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    """
    Returns the process-wide Settings instance, constructed once and cached.
    Tests that need to vary the environment should call
    get_settings.cache_clear() after monkeypatching env vars.
    """
    return Settings()
