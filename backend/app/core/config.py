"""Application settings, loaded from environment variables (and an optional .env file).

pydantic-settings reads each field from an env var with the same name (case-insensitive),
so `DATABASE_URL=...` fills `settings.database_url`. Every value has a safe default for
local development except `SECRET_KEY`, which you must change in production.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- general ---
    app_name: str = "Flowboard API"
    environment: str = "development"  # development | test | production
    api_prefix: str = "/api/v1"

    # --- infrastructure ---
    database_url: str = "postgresql+asyncpg://flowboard:flowboard@localhost:55433/flowboard"
    redis_url: str = "redis://localhost:56379/0"

    # --- security ---
    secret_key: str = "dev-only-change-me-please-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    # bcrypt work factor: each +1 doubles the hashing time. Tests lower it for speed.
    bcrypt_rounds: int = 12

    # Login rate limit: at most `login_rate_limit` attempts per `login_rate_window_seconds`
    # for the same client IP + email.
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60

    # --- HTTP ---
    # NoDecode: read the raw string so the validator below can split "a,b" into a list.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5183",
        "http://127.0.0.1:5183",
    ]

    # --- uploads ---
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    # --- logging ---
    log_level: str = "INFO"
    log_json: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        """Allow CORS_ORIGINS to be a comma separated string in .env files."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings instance (cached, so the env is read only once)."""
    return Settings()


settings = get_settings()
