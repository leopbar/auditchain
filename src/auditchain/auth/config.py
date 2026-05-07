"""Authentication specific configuration."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Configuration for JWT and password security."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # JWT Security
    # In production, this MUST be a strong, random string
    secret_key: SecretStr = Field(default=SecretStr("development-secret-key-change-me"))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


@lru_cache
def get_auth_settings() -> AuthSettings:
    """Cached auth settings instance."""
    return AuthSettings()
