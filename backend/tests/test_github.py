from __future__ import annotations

from app.services.github import GithubService


class DummyResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")


def test_get_repo_metadata_uses_github_api(monkeypatch):
    service = GithubService()
    calls: list[tuple[str, dict]] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers or {}))
        return DummyResponse(200, {"default_branch": "main"})

    monkeypatch.setattr("app.services.github.requests.get", fake_get)

    metadata = service.get_repo_metadata("octocat", "hello-world")

    assert metadata["default_branch"] == "main"
    assert calls[0][0].endswith("/repos/octocat/hello-world")
    assert calls[0][1]["Accept"] == "application/vnd.github+json"


def test_get_file_tree_filters_and_caps_results(monkeypatch):
    service = GithubService()
    payload = {
        "tree": [
            {"type": "blob", "path": "src/app.py", "size": 10},
            {"type": "blob", "path": "src/__init__.py", "size": 10},
            {"type": "blob", "path": "docs/readme.md", "size": 10},
            {"type": "blob", "path": "src/large.py", "size": 200_000},
        ]
        + [{"type": "blob", "path": f"src/file_{index}.py", "size": 10} for index in range(350)]
    }

    monkeypatch.setattr("app.services.github.requests.get", lambda *args, **kwargs: DummyResponse(200, payload))

    files = service.get_file_tree("octocat", "hello-world", "main")

    assert files[0]["path"] == "src/app.py"
    assert all(item["path"] != "src/__init__.py" for item in files)
    assert len(files) == 300


def test_get_file_content_returns_raw_text(monkeypatch):
    service = GithubService()

    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(200, text="print('hello')")

    monkeypatch.setattr("app.services.github.requests.get", fake_get)

    assert service.get_file_content("octocat", "hello-world", "main", "src/app.py") == "print('hello')"
