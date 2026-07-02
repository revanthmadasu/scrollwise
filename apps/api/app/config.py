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

    # Content-generation trigger (event-driven Fargate, prod). On prompt submit
    # the API fires an ECS RunTask so the generator drains the new row promptly —
    # no scheduler/polling. Leave `ecs_cluster` empty (dev) to disable the
    # trigger: the `user_prompts` row is still the queue, drained by a local
    # poller instead. See services/content-generator + infra/aws/generator/.
    aws_region: str = "us-east-1"
    ecs_cluster: str = ""
    ecs_task_definition: str = "scrollwise-generator"
    ecs_subnets: str = ""          # comma-separated subnet ids the task runs in
    ecs_security_groups: str = ""  # comma-separated security-group ids
    # "ENABLED" when the task runs in a PUBLIC subnet (free IGW egress — the task
    # needs a public IP to use it). "DISABLED" for private subnets (egress via
    # NAT / VPC endpoints). See infra/aws/generator/.
    ecs_assign_public_ip: str = "DISABLED"

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
    def ecs_subnet_list(self) -> list[str]:
        return [s.strip() for s in self.ecs_subnets.split(",") if s.strip()]

    @property
    def ecs_security_group_list(self) -> list[str]:
        return [s.strip() for s in self.ecs_security_groups.split(",") if s.strip()]

    @property
    def generation_trigger_enabled(self) -> bool:
        """True when the event-driven Fargate trigger is configured (prod)."""
        return bool(self.ecs_cluster and self.ecs_subnet_list)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    return Settings()
