from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI

import app.main as main_module


def test_raises_in_production_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    async def _nop():
        return None
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", None)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="API_KEY must be set when APP_ENV=production"):
        asyncio.run(runner())


def test_no_raise_in_development_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    async def _nop():
        return None
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(main_module.settings, "API_KEY", None)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    # Should not raise
    asyncio.run(runner())


def test_requires_github_token_in_production_when_api_key_present(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    async def _nop():
        return None
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", "present")
    monkeypatch.setattr(main_module.settings, "GITHUB_TOKEN", None)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN must be set when APP_ENV=production"):
        asyncio.run(runner())


def test_no_raise_in_production_when_both_keys_present(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)
    async def _nop():
        return None
    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", "present")
    monkeypatch.setattr(main_module.settings, "GITHUB_TOKEN", "present")

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    # Should not raise
    asyncio.run(runner())
