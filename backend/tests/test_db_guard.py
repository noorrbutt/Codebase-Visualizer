from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI

import app.main as main_module


def test_production_sqlite_is_rejected(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)

    async def _nop():
        return None

    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", "present")
    monkeypatch.setattr(main_module.settings, "GITHUB_TOKEN", "present")
    monkeypatch.setattr(main_module.settings, "DATABASE_URL", "sqlite:///backend/codebase_visualizer.db")

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="Postgres required in production, sqlite is dev-only"):
        asyncio.run(runner())
