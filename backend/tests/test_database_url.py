from __future__ import annotations

from app.config import Settings


def test_postgres_scheme_is_rewritten_to_postgresql():
    settings = Settings(DATABASE_URL="postgres://user:pw@host.neon.tech/db?sslmode=require")

    assert settings.DATABASE_URL == "postgresql://user:pw@host.neon.tech/db?sslmode=require"


def test_postgresql_scheme_is_left_unchanged():
    url = "postgresql://user:pw@host.neon.tech/db"

    assert Settings(DATABASE_URL=url).DATABASE_URL == url


def test_sqlite_url_is_left_unchanged():
    url = "sqlite:////tmp/codebase_visualizer.db"

    assert Settings(DATABASE_URL=url).DATABASE_URL == url
