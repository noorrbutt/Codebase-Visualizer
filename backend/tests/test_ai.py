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


def test_analyze_file_normalizes_and_limits_ai_fields():
    service = AIService()

    class FakeResponse:
        def __init__(self, content):
            class Message:
                def __init__(self, value):
                    self.content = value

            class Choice:
                def __init__(self, message):
                    self.message = message

            self.choices = [Choice(Message(content))]

    class Completions:
        @staticmethod
        def create(*args, **kwargs):
            import json

            return FakeResponse(json.dumps({
                "summary": f"  {'s' * 650}  ",
                "summary_detail": f"  {'d' * 610}  ",
                "complexity": " HIGH ",
                "role": "API Router",
            }))

    class Chat:
        completions = Completions()

    service.client = type("C", (), {"chat": Chat()})()

    result = service._call_analyze_file("file.py", "content")

    assert result == {
        "summary": "s" * 600,
        "summary_detail": "d" * 600,
        "complexity": "high",
        "role": "api_router",
    }


def test_analyze_file_uses_safe_defaults_for_unknown_ai_categories():
    service = AIService()

    class FakeResponse:
        def __init__(self):
            class Message:
                content = '{"summary":" summary ","summary_detail":" detail ","complexity":"extreme","role":"new kind"}'

            class Choice:
                message = Message()

            self.choices = [Choice()]

    class Completions:
        @staticmethod
        def create(*args, **kwargs):
            return FakeResponse()

    class Chat:
        completions = Completions()

    service.client = type("C", (), {"chat": Chat()})()

    result = service._call_analyze_file("file.py", "content")

    assert result == {
        "summary": "summary",
        "summary_detail": "detail",
        "complexity": "medium",
        "role": "unknown",
    }


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