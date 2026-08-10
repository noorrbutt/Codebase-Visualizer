from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI

import app.main as main_module


def test_raises_in_production_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", lambda: None)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", None)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="API_KEY must be set when APP_ENV=production"):
        asyncio.run(runner())


def test_no_raise_in_development_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", lambda: None)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(main_module.settings, "API_KEY", None)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    # Should not raise
    asyncio.run(runner())
