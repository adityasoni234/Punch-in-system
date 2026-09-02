"""Application configuration.

Every value is environment driven. Nothing security relevant is hardcoded.
Business rules that an administrator must be able to change at runtime
(geofence radius, accuracy threshold, timezone, ...) do NOT live here --
they live in the `workspaces` table. This module only holds infrastructure
and security configuration.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEV_KEY = "CHANGE_ME_INSECURE_DEVELOPMENT_KEY_DO_NOT_USE_IN_PRODUCTION"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application ------------------------------------------------------
    app_name: str = "Punch In System"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = False

    # -- Database ---------------------------------------------------------
    database_url: str = "postgresql+psycopg://punchin:punchin@localhost:5432/punchin"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    sql_echo: bool = False

    # -- Security ---------------------------------------------------------
    secret_key: str = INSECURE_DEV_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None
    refresh_cookie_name: str = "punchin_refresh"

    cors_origins: str = ""

    # -- Rate limiting ----------------------------------------------------
    rate_limit_login_max: int = 5
    rate_limit_login_window_seconds: int = 900
    rate_limit_punch_max: int = 10
    rate_limit_punch_window_seconds: int = 60
    rate_limit_global_max: int = 300
    rate_limit_global_window_seconds: int = 60

    # -- Registration -----------------------------------------------------
    # Self sign up is convenient but means anyone who reaches the app can
    # create an account. Turn it off to make accounts admin-issued only.
    allow_self_registration: bool = True

    # -- Privacy ----------------------------------------------------------
    location_retention_days: int = 180

    # -- Proxy ------------------------------------------------------------
    trust_proxy_headers: bool = False

    # -- Startup ----------------------------------------------------------
    # Platforms without a release phase (Render, Fly, plain containers) need
    # the schema applied as the container boots. Off by default so a local run
    # never migrates a database behind your back.
    run_migrations_on_start: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_database_url(cls, v: object) -> object:
        """Accept the URL shape hosted providers actually hand out.

        Neon, Supabase, Render and Heroku all issue `postgres://` or
        `postgresql://` URLs. Neither selects the psycopg3 driver this app
        uses, and the resulting failure ("Can't load plugin") says nothing
        useful, so rewrite the scheme rather than making every deployment
        remember to.
        """
        if not isinstance(v, str) or not v:
            return v
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def _blank_domain_is_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def validate_runtime(self) -> None:
        """Fail loudly rather than run insecurely."""
        if self.is_production:
            problems: list[str] = []
            if self.secret_key == INSECURE_DEV_KEY or len(self.secret_key) < 32:
                problems.append(
                    "SECRET_KEY must be set to a strong random value in production "
                    '(python -c "import secrets;print(secrets.token_urlsafe(64))")'
                )
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true in production (HTTPS only)")
            if self.debug:
                problems.append("DEBUG must be false in production")
            if problems:
                raise RuntimeError(
                    "Refusing to start with an insecure configuration:\n  - "
                    + "\n  - ".join(problems)
                )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "test" and settings.secret_key == INSECURE_DEV_KEY:
        # Tests get an ephemeral key so no test ever depends on a fixed secret.
        settings.secret_key = secrets.token_urlsafe(64)
    return settings


settings = get_settings()
