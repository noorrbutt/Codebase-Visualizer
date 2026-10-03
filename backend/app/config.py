import json
from typing import Annotated

from pydantic import field_validator
from pathlib import Path
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str | None = None
    # Server-side only: keep this out of browser code and public routes.
    API_KEY: str | None = None
    # Default to a DB file placed inside the backend directory regardless of cwd.
    _default_db_path = Path(__file__).resolve().parent.parent / "codebase_visualizer.db"
    DATABASE_URL: str = f"sqlite:///{_default_db_path.as_posix()}"
    GITHUB_TOKEN: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    # NoDecode stops pydantic-settings from parsing the env value as JSON first, so both
    # "https://a.com,https://b.com" and '["https://a.com"]' reach the validator below.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000"]
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20
    MAX_REPO_FILES: int = 300
    MAX_CONCURRENT_REPO_ANALYSES: int = 5
    TRUST_PROXY_HEADERS: bool = False
    # Number of trusted proxies appending to X-Forwarded-For; the client IP is the entry this many positions from the right.
    TRUSTED_PROXY_COUNT: int = 0
    # Number of seconds after which a repo lock is considered stale and may be reclaimed
    RECLAIM_LOCK_AFTER_SECONDS: int = 600
    AI_MAX_REQUESTS_PER_HOUR: int = 60
    AI_MAX_REQUESTS_PER_DAY: int = 200
    AI_MAX_CLIENT_REQUESTS_PER_HOUR: int = 1000
    AI_MAX_CLIENT_REQUESTS_PER_DAY: int = 4000

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # SQLAlchemy 2 only accepts the "postgresql://" scheme; hosted providers often issue "postgres://".
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://"):]
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
