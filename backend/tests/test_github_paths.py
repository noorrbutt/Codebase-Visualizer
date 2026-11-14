from unittest.mock import patch

import pytest
import requests

from app.exceptions import RepoParseError
from app.services.github import GithubService


def test_get_file_content_encodes_path_and_fetches():
    svc = GithubService()
    owner = "owner"
    repo = "repo"
    branch = "main"
    # path contains a space and a '#', both must be percent-encoded
    path = "dir/file name#section.py"

    called_urls = []

    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"file-content"
        return resp

    with patch("app.services.github.requests.get", new=fake_get):
        content = svc.get_file_content(owner, repo, branch, path)

    assert content == "file-content"
    assert called_urls, "requests.get was not called"
    # ensure path is percent-encoded in the called URL
    assert "%20" in called_urls[0]
    assert "%23" in called_urls[0]


def test_rejects_dotdot_segment():
    svc = GithubService()

    with pytest.raises(RepoParseError, match=r"path.*\.\."):
        svc.get_file_content("owner", "repo", "main", "src/../lib/util.py")


def test_rejects_leading_slash():
    svc = GithubService()

    with pytest.raises(RepoParseError, match=r"path.*start with '/'|path.*leading slash"):
        svc.get_file_content("owner", "repo", "main", "/absolute/path.py")


def test_rejects_empty_path():
    svc = GithubService()

    with pytest.raises(RepoParseError, match=r"path.*empty"):
        svc.get_file_content("owner", "repo", "main", "")


def test_accepts_normal_nested_path():
    svc = GithubService()
    owner = "owner"
    repo = "repo"
    branch = "main"
    path = "src/app/views/user_profile.py"

    called_urls = []

    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        resp = requests.Response()
        resp.status_code = 200
        resp._content = b"nested-content"
        return resp

    with patch("app.services.github.requests.get", new=fake_get):
        content = svc.get_file_content(owner, repo, branch, path)

    assert content == "nested-content"
    assert called_urls
    assert "src/app/views/user_profile.py" in called_urls[0]


def test_commit_sha_is_accepted_for_tree_and_raw_file_urls():
    svc = GithubService()
    sha = "0123456789abcdef0123456789abcdef01234567"
    called_urls = []

    def fake_get(url, headers=None, timeout=None):
        called_urls.append(url)
        resp = requests.Response()
        resp.status_code = 200
        if "/git/trees/" in url:
            resp._content = b'{"tree":[]}'
        else:
            resp._content = b"file-content"
        return resp

    with patch("app.services.github.requests.get", new=fake_get):
        assert svc.get_file_tree("owner", "repo", sha) == []
        assert svc.get_file_content("owner", "repo", sha, "src/app.py") == "file-content"

    assert called_urls[0] == (
        f"https://api.github.com/repos/owner/repo/git/trees/{sha}?recursive=1"
    )
    assert called_urls[1] == (
        f"https://raw.githubusercontent.com/owner/repo/{sha}/src/app.py"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Owner/Repo",
        "https://github.com/Owner/Repo.git",
        "https://github.com/Owner/Repo/tree/main",
        "https://www.github.com/Owner/Repo",
        "https://github.com/Owner/Repo/?tab=readme",
    ],
)
def test_parse_repo_url_accepts_repository_url_variants(url):
    svc = GithubService()

    assert svc.parse_repo_url(url) == ("Owner", "Repo")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/../user",
        "https://github.com/./user",
        "https://github.com/%2e%2e/user",
        "https://github.com/.hidden/repo",
        "https://github.com/a/..",
        "",
    ],
)
def test_parse_repo_url_rejects_dot_segments_and_empty_url(url):
    with pytest.raises(RepoParseError):
        GithubService().parse_repo_url(url)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/pallets/flask", ("pallets", "flask")),
        ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
    ],
)
def test_parse_repo_url_accepts_valid_github_names(url, expected):
    assert GithubService().parse_repo_url(url) == expected
