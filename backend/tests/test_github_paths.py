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
