from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse
import urllib.parse

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
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0
_TRANSIENT_STATUS_CODES = {500, 502, 503, 504}
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")


class GithubService:
    def _sleep_before_retry(self, attempt: int) -> None:
        delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
        logger.warning("Transient GitHub failure, retrying in {} seconds (attempt {}/{})", delay, attempt + 1, _RETRY_ATTEMPTS)
        time.sleep(delay)

    def _request_with_retry(self, url: str) -> requests.Response:
        last_exception: requests.RequestException | None = None

        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                response = requests.get(url, headers=self._get_headers(), timeout=10)
            except requests.RequestException as exc:
                last_exception = exc
                if attempt == _RETRY_ATTEMPTS:
                    raise
                self._sleep_before_retry(attempt)
                continue

            if response.status_code in _TRANSIENT_STATUS_CODES:
                logger.warning(
                    "GitHub returned transient status %s for %s (attempt %s/%s)",
                    response.status_code,
                    url,
                    attempt,
                    _RETRY_ATTEMPTS,
                )
                if attempt == _RETRY_ATTEMPTS:
                    response.raise_for_status()
                self._sleep_before_retry(attempt)
                continue

            return response

        if last_exception is not None:
            raise last_exception

        raise requests.RequestException(f"GitHub request failed for {url}")

    def _raise_for_rate_limit(self, response: requests.Response, owner: str, repo: str) -> None:
        payload = response.json()
        message = payload.get("message", "")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        reset_time = "later"

        if reset:
            try:
                reset_time = datetime.fromtimestamp(int(reset), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (TypeError, ValueError):
                reset_time = reset

        lower_message = message.lower()
        if response.status_code == 403 and remaining == "0":
            raise GithubRateLimitError(
                f"GitHub API rate limit exceeded, try again after {reset_time}"
            )

        if (
            response.status_code == 403
            and (
                response.headers.get("Retry-After") is not None
                or "secondary rate limit" in lower_message
                or "abuse detection" in lower_message
            )
        ):
            raise GithubRateLimitError(
                "GitHub API secondary rate limit or abuse detection triggered, retry after the delay indicated by GitHub"
            )

        if "rate limit" in lower_message:
            raise GithubRateLimitError(
                f"GitHub API rate limit exceeded, try again after {reset_time}"
            )

        raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

    def _validate_branch(self, branch: str) -> None:
        if not branch:
            raise RepoParseError("branch name must not be empty")

        if len(branch) > 255:
            raise RepoParseError("branch name is too long")

        if ".." in branch:
            raise RepoParseError("branch name may not contain '..'")

        if branch.startswith("/"):
            raise RepoParseError("branch name may not start with '/'")

        if not _BRANCH_RE.fullmatch(branch):
            raise RepoParseError("branch name may only contain letters, numbers, underscore, dot, hyphen, or slash")

    def _validate_file_path(self, path: str) -> None:
        if not path:
            raise RepoParseError("file path must not be empty")

        if path.startswith("/"):
            raise RepoParseError("file path may not start with '/'")

        if "\x00" in path:
            raise RepoParseError("file path may not contain null bytes")

        if any(segment == ".." for segment in path.split("/")):
            raise RepoParseError("file path may not contain '..' path segments")

    def _get_headers(self) -> dict:
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}

        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

        return headers

    def get_repo_metadata(self, owner: str, repo: str) -> dict:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        logger.info("Calling GitHub repo metadata API: {}", url)
        response = self._request_with_retry(url)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            self._raise_for_rate_limit(response, owner, repo)

        if response.status_code == 401:
            raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

        response.raise_for_status()

        metadata = response.json()
        logger.info("GitHub repo metadata received for {}/{}", owner, repo)
        return metadata

    def get_file_tree(self, owner: str, repo: str, branch: str) -> list[dict]:
        # Branch names currently come from GitHub metadata responses, but this validation
        # provides defense in depth if future callers pass a custom branch value.
        self._validate_branch(branch)

        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        logger.info("Fetching GitHub tree: {}", url)
        response = self._request_with_retry(url)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            self._raise_for_rate_limit(response, owner, repo)

        if response.status_code == 401:
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

        logger.info("Filtered GitHub tree to {} supported files", len(filtered))
        capped = filtered[: settings.MAX_REPO_FILES]
        if len(filtered) > settings.MAX_REPO_FILES:
            logger.warning("Capping repository analysis to {} files from {} discovered files", len(capped), len(filtered))
        return capped

    def get_file_content(self, owner: str, repo: str, branch: str, path: str) -> str:
        # Branch names currently come from GitHub metadata responses, but this validation
        # provides defense in depth if future callers pass a custom branch value.
        self._validate_branch(branch)
        self._validate_file_path(path)
        # Percent-encode the file path to ensure spaces, #, %, unicode, etc. are safe in the URL.
        encoded_path = urllib.parse.quote(path, safe="/")
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{encoded_path}"
        logger.info("Fetching raw file content: {}", url)
        response = self._request_with_retry(url)
        response.raise_for_status()
        return response.text

    def fetch_files_concurrent(self, owner: str, repo: str, branch: str, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        logger.info("Fetching {} files concurrently", len(paths))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.get_file_content, owner, repo, branch, path): path for path in paths}

            for future in as_completed(futures):
                path = futures[future]
                try:
                    contents[path] = future.result()
                except requests.RequestException as exc:
                    logger.warning("Failed to fetch {}: {}", path, exc)
                except Exception as exc:
                    logger.warning("Unexpected failure while fetching {}: {}", path, exc)

        logger.info("Completed concurrent file fetch, successful={}", len(contents))
        return contents

    def parse_repo_url(self, url: str) -> tuple[str, str]:
        logger.info("Parsing GitHub URL: {}", url)
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

        if not _NAME_RE.fullmatch(owner) or not _NAME_RE.fullmatch(repo):
            raise RepoParseError("owner and repository names may only contain letters, numbers, underscore, dot, or hyphen")

        return owner, repo
