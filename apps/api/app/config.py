"""Application settings, loaded from environment / .env (mirrors the
content-generator's dotenv style)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database — shared with the content-generator. See .env.example.
    database_url: str = "sqlite+aiosqlite:///../../services/content-generator/data/content.db"

    # Auth
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 30

    # Google OIDC
    google_client_id: str = ""
    google_client_secret: str = ""

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Logging. Logs always go to stderr; set log_file to also write to a
    # rotating file (mirrors the content-generator's CONTENT_GEN_LOG_FILE).
    log_file: str = ""
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
