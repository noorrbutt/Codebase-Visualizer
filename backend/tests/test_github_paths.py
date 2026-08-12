from unittest.mock import patch

import requests

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
