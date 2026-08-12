from __future__ import annotations

import asyncio

from app.services.ai import AIService
from tests.conftest import InMemoryRedis


def test_analyze_file_retries_on_json_validate(monkeypatch):
    service = AIService()

    # Provide an in-memory redis so budget checks pass
    service._redis_client = InMemoryRedis()

    # Capture create() kwargs and simulate first-call failure, second-call success
    create_calls = {"count": 0}
    captured_kwargs = []

    class FakeResponse:
        def __init__(self, text):
            class Msg:
                def __init__(self, content):
                    self.content = content

            class Choice:
                def __init__(self, msg):
                    self.message = msg

            self.choices = [Choice(Msg(text))]
            self.usage = {"tokens": 42}

    def fake_create(*args, **kwargs):
        create_calls["count"] += 1
        captured_kwargs.append(kwargs)
        if create_calls["count"] == 1:
            e = Exception("json_validate_failed")
            e.body = {"error": {"code": "json_validate_failed"}}
            raise e
        return FakeResponse('{"summary":"s","summary_detail":"d","complexity":"low","role":"utility"}')

    # Hook the fake client onto the service
    class Completions:
        create = staticmethod(fake_create)

    class Chat:
        completions = Completions()

    service.client = type("C", (), {"chat": Chat()})()

    result = asyncio.run(service.analyze_file("/tmp/file.py", "print(\"hi\")\n" * 10))

    assert create_calls["count"] == 2
    # Ensure max_tokens was set to 900 in the create kwargs
    assert captured_kwargs[0]["max_tokens"] == 900
    assert result["summary"] == "s"
    assert result["complexity"] == "low"


def test_analyze_file_retries_on_malformed_json(monkeypatch):
    service = AIService()
    service._redis_client = InMemoryRedis()

    create_calls = {"count": 0}

    class FakeResponse:
        def __init__(self, text):
            class Msg:
                def __init__(self, content):
                    self.content = content

            class Choice:
                def __init__(self, msg):
                    self.message = msg

            self.choices = [Choice(Msg(text))]

    def fake_create(*args, **kwargs):
        create_calls["count"] += 1
        if create_calls["count"] == 1:
            # return truncated/invalid JSON to trigger JSONDecodeError -> AIMalformedResponseError
            return FakeResponse('{"summary": "s",')
        return FakeResponse('{"summary":"s","summary_detail":"d","complexity":"low","role":"utility"}')

    class Completions:
        create = staticmethod(fake_create)

    class Chat:
        completions = Completions()

    service.client = type("C", (), {"chat": Chat()})()

    try:
        asyncio.run(service.analyze_file("/tmp/file.py", "print(\"hi\")\n" * 10))
        assert False, "Expected AIServiceError"
    except Exception as exc:
        # Malformed model output should not be retried by default
        assert create_calls["count"] == 1
        from app.exceptions import AIServiceError

        assert isinstance(exc, AIServiceError)
        assert "invalid_json" in str(exc)


def test_analyze_file_does_not_retry_on_unrelated_exception(monkeypatch):
    service = AIService()
    service._redis_client = InMemoryRedis()

    create_calls = {"count": 0}

    def fake_create(*args, **kwargs):
        create_calls["count"] += 1
        raise ValueError("unexpected failure")

    class Completions:
        create = staticmethod(fake_create)

    class Chat:
        completions = Completions()

    service.client = type("C", (), {"chat": Chat()})()

    try:
        asyncio.run(service.analyze_file("/tmp/file.py", "print(\"hi\")\n" * 10))
        assert False, "Expected AIServiceError"
    except Exception as exc:
        # ensure we surfaced as AIServiceError and only one attempt was made
        assert create_calls["count"] == 1
        from app.exceptions import AIServiceError

        assert isinstance(exc, AIServiceError)