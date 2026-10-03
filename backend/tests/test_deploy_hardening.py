from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as main_module
import app.services.redis_client as redis_module
from app.config import Settings


def test_cors_origins_accepts_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example,https://b.example")

    assert Settings().CORS_ORIGINS == ["https://a.example", "https://b.example"]


def test_cors_origins_accepts_json_array_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')

    assert Settings().CORS_ORIGINS == ["https://a.example"]


def test_production_refuses_trusted_proxy_headers_without_proxy_count(monkeypatch):
    monkeypatch.setattr(main_module, "create_tables", lambda: None)

    async def _nop():
        return None

    monkeypatch.setattr(main_module, "resume_pending_repo_analyses", _nop)
    monkeypatch.setattr(main_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(main_module.settings, "API_KEY", "test-key")
    monkeypatch.setattr(main_module.settings, "GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(main_module.settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(main_module.settings, "TRUSTED_PROXY_COUNT", 0)

    async def runner():
        async with main_module.lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="TRUSTED_PROXY_COUNT"):
        asyncio.run(runner())


def test_readiness_reports_generic_error_without_leaking_details(monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise RuntimeError("connection to secret-host.internal refused")

    monkeypatch.setattr(redis_module, "get_redis_client", lambda: BrokenRedis())

    response = TestClient(main_module.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "error"
    assert "secret-host" not in response.text
