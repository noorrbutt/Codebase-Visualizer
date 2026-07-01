from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

from app.config import settings
from app.exceptions import (
    GithubRateLimitError,
    RepoNotFoundError,
    RepoParseError,
    RepoPrivateError,
)
from app.logging import get_logger

logger = get_logger(__name__)
SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md"}
MAX_FILE_SIZE_BYTES = 102_400
DEFAULT_MAX_REPO_FILES = 300


class GithubService:
    def _get_headers(self) -> dict:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}

        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

        return headers

    def get_repo_metadata(self, owner: str, repo: str) -> dict:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        logger.info("Calling GitHub repo metadata API: %s", url)
        response = requests.get(url, headers=self._get_headers(), timeout=10)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            payload = response.json()
            message = payload.get("message", "")
            if "rate limit" in message.lower():
                raise GithubRateLimitError()

            raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

        response.raise_for_status()

        metadata = response.json()
        logger.info("GitHub repo metadata received for %s/%s", owner, repo)
        return metadata

    def get_file_tree(self, owner: str, repo: str, branch: str) -> list[dict]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        logger.info("Fetching GitHub tree: %s", url)
        response = requests.get(url, headers=self._get_headers(), timeout=10)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            payload = response.json()
            if "rate limit" in payload.get("message", "").lower():
                raise GithubRateLimitError()
            raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

        response.raise_for_status()

        tree = response.json().get("tree", [])
        filtered: list[dict] = []

        for item in tree:
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            if not path:
                continue

            extension = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if extension not in SUPPORTED_EXTENSIONS:
                continue

            path_lower = path.lower()
            if (
                "/migrations/" in path_lower
                or "/static/" in path_lower
                or "/docs/" in path_lower
                or "/.github/" in path_lower
            ):
                continue

            basename = path_lower.rsplit("/", 1)[-1]
            if basename in {"__init__.py", "manage.py"}:
                continue

            size = item.get("size")
            if size is None or size > MAX_FILE_SIZE_BYTES:
                continue

            filtered.append(item)

        logger.info("Filtered GitHub tree to %s supported files", len(filtered))
        capped = filtered[: settings.MAX_REPO_FILES]
        if len(filtered) > settings.MAX_REPO_FILES:
            logger.warning("Capping repository analysis to %s files from %s discovered files", len(capped), len(filtered))
        return capped

    def get_file_content(self, owner: str, repo: str, branch: str, path: str) -> str:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        logger.info("Fetching raw file content: %s", url)
        response = requests.get(url, headers=self._get_headers(), timeout=10)
        response.raise_for_status()
        return response.text

    def fetch_files_concurrent(self, owner: str, repo: str, branch: str, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        logger.info("Fetching %s files concurrently", len(paths))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.get_file_content, owner, repo, branch, path): path for path in paths}

            for future in as_completed(futures):
                path = futures[future]
                try:
                    contents[path] = future.result()
                except requests.RequestException as exc:
                    logger.warning("Failed to fetch %s: %s", path, exc)
                except Exception as exc:
                    logger.warning("Unexpected failure while fetching %s: %s", path, exc)

        logger.info("Completed concurrent file fetch, successful=%s", len(contents))
        return contents

    def parse_repo_url(self, url: str) -> tuple[str, str]:
        logger.info("Parsing GitHub URL: %s", url)
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"}:
            raise RepoParseError("URL must start with http:// or https://")

        if parsed.netloc.lower() != "github.com":
            raise RepoParseError("URL must point to github.com")

        parts = [segment for segment in parsed.path.strip("/").split("/") if segment]
        if len(parts) < 2:
            raise RepoParseError("URL must include owner and repository name")

        owner, repo = parts[0], parts[1].removesuffix(".git")
        if not owner or not repo:
            raise RepoParseError("URL must include owner and repository name")

        return owner, repo
