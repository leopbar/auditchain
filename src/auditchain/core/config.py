"""Application settings loaded from environment variables.

All configuration goes through this module. Never read os.environ directly
elsewhere in the codebase — it makes testing painful and hides config
dependencies.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM keys
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    # Models
    llm_fast_model: str = "gpt-4o-mini"
    llm_smart_model: str = "gpt-4o"
    llm_embedding_model: str = "text-embedding-3-small"

    # SEC EDGAR
    sec_user_agent: str = Field(
        default="AuditChain Research contact@example.com",
        description="SEC requires User-Agent identification on every request.",
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://auditchain:auditchain_dev@localhost:5432/auditchain"
    )
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "auditchain"
    postgres_password: SecretStr = SecretStr("auditchain_dev")
    postgres_db: str = "auditchain"

    # Observability
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "auditchain"
    langsmith_tracing: bool = False

    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None

    # App
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["development", "staging", "production"] = "development"

    # Cost guardrails
    max_tokens_per_run: int = 100_000
    max_cost_per_run_usd: float = 1.00

    # Paths
    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent.parent.parent

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_data_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_data_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def synthetic_data_dir(self) -> Path:
        return self.data_dir / "synthetic"

    @property
    def sync_database_url(self) -> str:
        """Synchronous version for Alembic and scripts."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Use this everywhere instead of instantiating Settings."""
    return Settings()
