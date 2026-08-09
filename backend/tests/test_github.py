from __future__ import annotations

import pytest
import requests

from app.exceptions import GithubRateLimitError, RepoNotFoundError, RepoParseError
from app.services.github import GithubService


class DummyResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


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


def test_fetch_files_concurrent_returns_contents_for_all_paths(monkeypatch):
    service = GithubService()
    calls: list[tuple[str, str]] = []

    def fake_get_file_content(self, owner, repo, branch, path):
        calls.append((branch, path))
        return f"content for {path}"

    monkeypatch.setattr(GithubService, "get_file_content", fake_get_file_content)

    paths = ["src/app.py", "src/utils.py", "README.md"]
    contents = service.fetch_files_concurrent("octocat", "hello-world", "main", paths)

    assert isinstance(contents, dict)
    assert len(contents) == 3
    assert contents == {
        "src/app.py": "content for src/app.py",
        "src/utils.py": "content for src/utils.py",
        "README.md": "content for README.md",
    }
    assert all(path in contents for path in paths)


def test_get_file_tree_accepts_branch_names_with_slashes(monkeypatch):
    service = GithubService()
    monkeypatch.setattr("app.services.github.requests.get", lambda *args, **kwargs: DummyResponse(200, {"tree": []}))

    assert service.get_file_tree("octocat", "hello-world", "release/1.0") == []


def test_get_repo_metadata_retries_transient_503_then_succeeds(monkeypatch):
    service = GithubService()
    responses = [DummyResponse(503, {"message": "Service Unavailable"}), DummyResponse(200, {"default_branch": "main"})]
    calls: list[tuple[str, dict]] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers or {}))
        return responses.pop(0)

    monkeypatch.setattr("app.services.github.requests.get", fake_get)

    metadata = service.get_repo_metadata("octocat", "hello-world")

    assert metadata["default_branch"] == "main"
    assert len(calls) == 2


def test_get_repo_metadata_fails_fast_on_404_without_retry(monkeypatch):
    service = GithubService()
    calls = 0

    def fake_get(url, headers=None, timeout=None):
        nonlocal calls
        calls += 1
        return DummyResponse(404, {"message": "Not Found"})

    monkeypatch.setattr("app.services.github.requests.get", fake_get)

    with pytest.raises(RepoNotFoundError):
        service.get_repo_metadata("octocat", "hello-world")

    assert calls == 1


def test_get_repo_metadata_raises_specific_rate_limit_message(monkeypatch):
    service = GithubService()

    def fake_get(url, headers=None, timeout=None):
        return DummyResponse(
            403,
            {"message": "API rate limit exceeded for 1.2.3.4."},
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1760000000"},
        )

    monkeypatch.setattr("app.services.github.requests.get", fake_get)

    with pytest.raises(GithubRateLimitError, match="GitHub API rate limit exceeded") as exc_info:
        service.get_repo_metadata("octocat", "hello-world")

    assert "try again after" in str(exc_info.value)


@pytest.mark.parametrize("branch", ["feature..x", "bad branch", "\n", ""])
def test_branch_validation_rejects_invalid_names(branch):
    service = GithubService()

    with pytest.raises(RepoParseError):
        service.get_file_tree("octocat", "hello-world", branch)

    with pytest.raises(RepoParseError):
        service.get_file_content("octocat", "hello-world", branch, "src/app.py")
