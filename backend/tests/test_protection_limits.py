import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.repos import _require_api_key
from app.config import settings
import app.services.ai as ai_module
from app.exceptions import AIServiceError
from app.services.ai import AIService
from app.services.github import GithubService
from app.services.rate_limit import IPRateLimiter


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")


class DummyGroqMessage:
    def __init__(self, content: str):
        self.content = content


class DummyGroqChoice:
    def __init__(self, content: str):
        self.message = DummyGroqMessage(content)


class DummyGroqResponse:
    def __init__(self, content: str):
        self.choices = [DummyGroqChoice(content)]
        self.usage = None


class FakeRedis:
    def __init__(self):
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, ttl: int) -> bool:
        self.expirations[key] = ttl
        return True

    def get(self, key: str):
        value = self.values.get(key)
        return None if value is None else str(value)


class DummyGroqCompletions:
    def __init__(self, handler):
        self._handler = handler

    def create(self, *args, **kwargs):
        return self._handler(*args, **kwargs)


class DummyGroqChat:
    def __init__(self, handler):
        self.completions = DummyGroqCompletions(handler)


class DummyGroqClient:
    def __init__(self, handler):
        self.chat = DummyGroqChat(handler)


def test_github_service_caps_large_file_tree(monkeypatch):
    service = GithubService()
    tree_payload = {
        "tree": [
            {"type": "blob", "path": f"src/file_{index}.py", "size": 10}
            for index in range(350)
        ]
    }

    monkeypatch.setattr("app.services.github.requests.get", lambda *args, **kwargs: DummyResponse(200, tree_payload))

    capped_files = service.get_file_tree("octocat", "hello-world", "main")

    assert len(capped_files) == 300
    assert capped_files[0]["path"] == "src/file_0.py"
    assert capped_files[-1]["path"] == "src/file_299.py"


def test_rate_limiter_blocks_excess_requests():
    limiter = IPRateLimiter(max_requests=2, window_seconds=60, redis_client=FakeRedis())

    assert limiter.allow("203.0.113.1") is True
    assert limiter.allow("203.0.113.1") is True
    assert limiter.allow("203.0.113.1") is False


def test_rate_limiter_uses_forwarded_for_header():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.7, 10.0.0.1"},
        client=SimpleNamespace(host="203.0.113.5"),
    )

    assert IPRateLimiter.resolve_client_ip(request) == "198.51.100.7"


def test_ai_service_enforces_budget_limits():
    service = AIService(hourly_limit=1, daily_limit=1, redis_client=FakeRedis())

    service.ensure_budget_available()

    with pytest.raises(AIServiceError):
        service.ensure_budget_available()


def test_ai_service_uses_redis_budgets(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(ai_module, "get_redis_client", lambda: fake_redis)

    first_service = AIService(hourly_limit=1, daily_limit=1)
    second_service = AIService(hourly_limit=1, daily_limit=1)

    first_service.ensure_budget_available()

    with pytest.raises(AIServiceError):
        second_service.ensure_budget_available()


def test_repo_api_key_dependency(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "secret-token")

    _require_api_key("secret-token")

    with pytest.raises(HTTPException):
        _require_api_key(None)

    with pytest.raises(HTTPException):
        _require_api_key("wrong-token")


def test_ai_service_retries_with_async_sleep_and_timeout(monkeypatch):
    service = AIService(hourly_limit=10, daily_limit=10)
    service.client = object()
    service.ensure_budget_available = lambda: None

    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    class FakeRateLimitError(Exception):
        def __init__(self):
            super().__init__("too many requests")
            self.status_code = 429

    def fake_call_analyze_file(*args, **kwargs):
        raise FakeRateLimitError()

    monkeypatch.setattr(ai_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(service, "_call_analyze_file", fake_call_analyze_file)

    with pytest.raises(AIServiceError):
        asyncio.run(service.analyze_file("foo.py", "print('hi')"))

    assert slept


def test_ai_service_does_not_retry_on_malformed_model_output(monkeypatch):
    service = AIService(hourly_limit=10, daily_limit=10)
    service.client = DummyGroqClient(
        lambda *args, **kwargs: DummyGroqResponse("```json\nnot actually json")
    )
    service.ensure_budget_available = lambda: None

    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(ai_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(AIServiceError) as exc_info:
        asyncio.run(service.analyze_file("foo.py", "print('hi')"))

    assert "invalid_json" in str(exc_info.value)
    assert slept == []


def test_ai_service_retries_only_on_actual_rate_limit_errors(monkeypatch):
    service = AIService(hourly_limit=10, daily_limit=10)
    service.client = object()
    service.ensure_budget_available = lambda: None

    slept: list[float] = []
    attempts = {"count": 0}

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    class FakeRateLimitError(Exception):
        def __init__(self):
            super().__init__("too many requests")
            self.status_code = 429

    def fake_call_analyze_file(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise FakeRateLimitError()
        return {
            "summary": "ok",
            "complexity": "low",
            "role": "utility",
        }

    monkeypatch.setattr(ai_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(service, "_call_analyze_file", fake_call_analyze_file)

    result = asyncio.run(service.analyze_file("foo.py", "print('hi')"))

    assert result["summary"] == "ok"
    assert attempts["count"] == 3
    assert len(slept) == 2


def test_ai_service_requests_structured_json_output(monkeypatch):
    service = AIService(hourly_limit=10, daily_limit=10)

    captured_kwargs = {}

    def fake_create(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return DummyGroqResponse('{"summary":"ok","complexity":"low","role":"utility"}')

    service.client = DummyGroqClient(fake_create)

    result = service._call_analyze_file("foo.py", "print('hi')")

    assert result == {
        "summary": "ok",
        "complexity": "low",
        "role": "utility",
    }
    assert captured_kwargs["response_format"] == {"type": "json_object"}


def test_ai_service_hourly_limit_three(fake_redis):
    service = AIService(hourly_limit=3, daily_limit=1000, redis_client=fake_redis)

    # first three calls should succeed
    service.ensure_budget_available()
    service.ensure_budget_available()
    service.ensure_budget_available()

    # fourth call exceeds hourly budget
    with pytest.raises(AIServiceError):
        service.ensure_budget_available()


def test_ai_service_daily_limit_persists_across_hourly_reset(fake_redis):
    service = AIService(hourly_limit=1000, daily_limit=2, redis_client=fake_redis)

    # two requests consume the daily budget
    service.ensure_budget_available()
    service.ensure_budget_available()

    # simulate hourly key expiring (advance clock past 1 hour)
    fake_redis.advance(3601)

    # next request should still count against daily budget and raise
    with pytest.raises(AIServiceError):
        service.ensure_budget_available()


def test_ip_rate_limiter_per_ip_isolation_and_burst_rejection(fake_redis):
    limiter = IPRateLimiter(max_requests=2, window_seconds=5, redis_client=fake_redis)

    # interleave requests across two IPs; each IP has independent counters
    assert limiter.allow("1.1.1.1") is True
    assert limiter.allow("1.1.1.1") is True
    assert limiter.allow("2.2.2.2") is True
    assert limiter.allow("2.2.2.2") is True

    # further requests for each IP are blocked independently
    assert limiter.allow("1.1.1.1") is False
    assert limiter.allow("2.2.2.2") is False


def test_ip_rate_limiter_burst_within_same_second(fake_redis):
    limiter = IPRateLimiter(max_requests=2, window_seconds=5, redis_client=fake_redis)

    results = [limiter.allow("203.0.113.10") for _ in range(3)]
    assert results == [True, True, False]
