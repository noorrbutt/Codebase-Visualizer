import pytest

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
    limiter = IPRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.allow("203.0.113.1") is True
    assert limiter.allow("203.0.113.1") is True
    assert limiter.allow("203.0.113.1") is False


def test_ai_service_enforces_budget_limits():
    service = AIService(hourly_limit=1, daily_limit=1)

    service.ensure_budget_available()

    with pytest.raises(AIServiceError):
        service.ensure_budget_available()
