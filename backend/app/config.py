"""Application settings, read from environment variables (or a local .env file)."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Turn a plain Postgres URL (as hosting providers give it) into an asyncpg URL.

    Hosted Postgres (Neon, Render, RDS ...) hands out ``postgresql://...?sslmode=require``.
    SQLAlchemy needs the ``postgresql+asyncpg://`` scheme, and asyncpg expects ``ssl=require``
    instead of libpq's ``sslmode`` / ``channel_binding`` options.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")

    if url.startswith("postgresql+asyncpg://") and "?" in url:
        base, query = url.split("?", 1)
        params = [p for p in query.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
        if "sslmode=require" in query:
            params.append("ssl=require")
        url = base + ("?" + "&".join(params) if params else "")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite works out of the box for local development, PostgreSQL in Docker / production.
    database_url: str = "sqlite+aiosqlite:///./servicequality.db"
    # No connection pool in tests (fresh event loop per test) and on serverless platforms (Vercel sets VERCEL=1),
    # where a pool would outlive the request; Neon handles short connections well.
    db_pool: bool = not os.environ.get("VERCEL")

    jwt_secret: str = "dev-only-secret-change-me-in-production"
    jwt_expire_minutes: int = 8 * 60  # one working shift
    bcrypt_rounds: int = 12

    cors_origins: str = "http://localhost:3000"

    auto_create_tables: bool = True  # the Docker image runs Alembic migrations instead (AUTO_CREATE_TABLES=false)
    seed_demo_data: bool = True

    max_upload_mb: int = 5
    max_import_rows: int = 20_000

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
