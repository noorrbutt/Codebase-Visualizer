from __future__ import annotations


class RepoNotFoundError(Exception):
    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url

    def __str__(self) -> str:
        return f"Repository not found: {self.repo_url}"


class RepoPrivateError(Exception):
    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url

    def __str__(self) -> str:
        return f"Repository is private or access is denied: {self.repo_url}"


class RepoParseError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"Invalid GitHub repository URL: {self.message}"


class GithubRateLimitError(Exception):
    def __str__(self) -> str:
        return "GitHub rate limit reached. Please provide a GITHUB_TOKEN or wait before retrying."


class AIServiceError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"AI service failure: {self.message}"
