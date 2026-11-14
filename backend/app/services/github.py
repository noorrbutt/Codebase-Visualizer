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
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_EXCLUDED_DIRECTORIES = {
    "docs",
    "static",
    "migrations",
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".github",
    "third_party",
}


class FileTreeResult(list[dict]):
    def __init__(
        self,
        files: list[dict],
        discovered_files: int,
        truncated: bool,
        dropped_file_extension_counts: dict[str, int],
    ) -> None:
        super().__init__(files)
        self.discovered_files = discovered_files
        self.truncated = truncated
        self.dropped_file_extension_counts = dropped_file_extension_counts


class GithubService:
    def __init__(self) -> None:
        self.dropped_file_extension_counts: dict[str, int] = {}

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

        if _COMMIT_SHA_RE.fullmatch(branch):
            return

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

    def get_commit_sha(self, owner: str, repo: str, branch: str) -> str:
        self._validate_branch(branch)
        encoded_branch = urllib.parse.quote(branch, safe="")
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{encoded_branch}"
        logger.info("Fetching GitHub commit: {}", url)
        response = self._request_with_retry(url)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            self._raise_for_rate_limit(response, owner, repo)

        if response.status_code == 401:
            raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

        response.raise_for_status()
        return response.json()["sha"]

    def get_file_tree(self, owner: str, repo: str, ref: str) -> FileTreeResult:
        self.dropped_file_extension_counts = {}
        self._validate_branch(ref)

        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
        logger.info("Fetching GitHub tree: {}", url)
        response = self._request_with_retry(url)

        if response.status_code == 404:
            raise RepoNotFoundError(f"https://github.com/{owner}/{repo}")

        if response.status_code == 403:
            self._raise_for_rate_limit(response, owner, repo)

        if response.status_code == 401:
            raise RepoPrivateError(f"https://github.com/{owner}/{repo}")

        response.raise_for_status()

        payload = response.json()
        tree = payload.get("tree", [])
        github_truncated = bool(payload.get("truncated", False))
        if github_truncated:
            logger.warning("GitHub truncated the repository tree for {}/{}", owner, repo)
        filtered: list[dict] = []
        dropped_extensions: dict[str, int] = {}

        def record_dropped_extension(path: str) -> None:
            basename = path.rsplit("/", 1)[-1]
            extension = (
                "." + basename.rsplit(".", 1)[-1].lower()
                if "." in basename
                else "(no extension)"
            )
            dropped_extensions[extension] = dropped_extensions.get(extension, 0) + 1

        for item in tree:
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            if not path:
                continue

            basename = path.rsplit("/", 1)[-1]
            extension = "." + basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
            if extension not in SUPPORTED_EXTENSIONS:
                record_dropped_extension(path)
                continue

            path_parts = path.split("/")
            directory_parts = [part.lower() for part in path_parts[:-1]]
            if any(part in _EXCLUDED_DIRECTORIES for part in directory_parts):
                record_dropped_extension(path)
                continue

            basename = path_parts[-1].lower()
            if basename.endswith((".min.js", ".d.ts")):
                record_dropped_extension(path)
                continue

            if basename == "manage.py":
                record_dropped_extension(path)
                continue

            size = item.get("size")
            if size is None or size > MAX_FILE_SIZE_BYTES:
                record_dropped_extension(path)
                continue
            if basename == "__init__.py" and size == 0:
                record_dropped_extension(path)
                continue

            filtered.append(item)

        def is_test_file(item: dict) -> bool:
            path_parts = item["path"].lower().split("/")
            basename = path_parts[-1]
            return (
                any(part in {"test", "tests", "__tests__"} for part in path_parts[:-1])
                or basename.startswith("test_")
                or ".test." in basename
                or ".spec." in basename
                or basename.endswith("_test.py")
            )

        filtered.sort(
            key=lambda item: (
                is_test_file(item),
                len(item["path"].split("/")),
                item["path"].lower(),
            )
        )
        discovered_files = len(filtered)
        logger.info("Filtered GitHub tree to {} supported files", discovered_files)
        capped = filtered[: settings.MAX_REPO_FILES]
        capped_files = filtered[settings.MAX_REPO_FILES :]
        for item in capped_files:
            record_dropped_extension(item["path"])
        self.dropped_file_extension_counts = dropped_extensions
        if capped_files:
            logger.warning(
                "Capping repository analysis to {} files from {} discovered files",
                len(capped),
                discovered_files,
            )
        return FileTreeResult(
            capped,
            discovered_files=discovered_files,
            truncated=github_truncated,
            dropped_file_extension_counts=dropped_extensions,
        )

    def get_file_content(self, owner: str, repo: str, ref: str, path: str) -> str:
        self._validate_branch(ref)
        self._validate_file_path(path)
        # Percent-encode the file path to ensure spaces, #, %, unicode, etc. are safe in the URL.
        encoded_path = urllib.parse.quote(path, safe="/")
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{encoded_path}"
        logger.info("Fetching raw file content: {}", url)
        response = self._request_with_retry(url)
        response.raise_for_status()
        return response.text

    def get_typescript_config(self, owner: str, repo: str, ref: str) -> str | None:
        for path in ("tsconfig.json", "jsconfig.json"):
            try:
                return self.get_file_content(owner, repo, ref, path)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    continue
                logger.warning("Failed to fetch {} for {}/{}: {}", path, owner, repo, exc)
                return None
            except requests.RequestException as exc:
                logger.warning("Failed to fetch {} for {}/{}: {}", path, owner, repo, exc)
                return None
        return None

    def fetch_files_concurrent(self, owner: str, repo: str, ref: str, paths: list[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        logger.info("Fetching {} files concurrently", len(paths))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.get_file_content, owner, repo, ref, path): path for path in paths}

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

        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise RepoParseError("URL must point to github.com")

        parts = [segment for segment in parsed.path.strip("/").split("/") if segment]
        if len(parts) < 2:
            raise RepoParseError("URL must include owner and repository name")

        owner = urllib.parse.unquote(parts[0])
        repo = urllib.parse.unquote(parts[1])
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo:
            raise RepoParseError("URL must include owner and repository name")

        if (
            owner in {".", ".."}
            or repo in {".", ".."}
            or owner.startswith(".")
            or repo.startswith(".")
            or not _OWNER_RE.fullmatch(owner)
            or not _REPO_RE.fullmatch(repo)
        ):
            raise RepoParseError("invalid GitHub owner or repository name")

        return owner, repo
