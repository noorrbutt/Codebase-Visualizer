from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str | None = None
    # Server-side only: keep this out of browser code and public routes.
    API_KEY: str | None = None
    DATABASE_URL: str = "sqlite:///./codebase_visualizer.db"
    GITHUB_TOKEN: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20
    MAX_REPO_FILES: int = 300
    AI_MAX_REQUESTS_PER_HOUR: int = 60
    AI_MAX_REQUESTS_PER_DAY: int = 200

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
