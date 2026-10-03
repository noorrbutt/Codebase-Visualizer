from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.files import router as files_router
from app.api.routes.repos import (
    initialize_repo_analysis_concurrency_gate,
    resume_pending_repo_analyses,
    router as repos_router,
)
from app.config import settings
from app.database import create_tables as _create_tables
from app.exceptions import (
    AIServiceError,
    GithubRateLimitError,
    RepoNotFoundError,
    RepoParseError,
    RepoPrivateError,
)
from app.logging import get_logger

logger = get_logger(__name__)


def create_tables() -> None:
    _create_tables()


def _validate_production_settings(settings) -> None:
    # Validate API_KEY presence
    if settings.API_KEY is None:
        if settings.APP_ENV == "production":
            raise RuntimeError("API_KEY must be set when APP_ENV=production")
        else:
            logger.warning("auth disabled - dev mode only")

    # Validate GITHUB_TOKEN presence
    if not settings.GITHUB_TOKEN:
        if settings.APP_ENV == "production":
            raise RuntimeError(
                "GITHUB_TOKEN must be set when APP_ENV=production to avoid shared 60req/hr GitHub limit"
            )
        else:
            logger.warning(
                "no GITHUB_TOKEN set - limited to 60 GitHub requests/hr, fine for local testing only"
            )

    # Warn when trusting X-Forwarded-For headers in production. Client IPs are only
    # reliable when TRUSTED_PROXY_COUNT matches the number of proxies that append to the header.
    if settings.TRUST_PROXY_HEADERS and settings.APP_ENV == "production":
        if settings.TRUSTED_PROXY_COUNT == 0:
            # Refuse to start: the leftmost X-Forwarded-For entry is client-controlled, so
            # trusting it in production makes IP rate limiting trivially bypassable.
            raise RuntimeError(
                "TRUST_PROXY_HEADERS=True requires TRUSTED_PROXY_COUNT >= 1 in production"
            )
        else:
            logger.warning(
                "TRUST_PROXY_HEADERS=True with TRUSTED_PROXY_COUNT={} - client IP is taken from X-Forwarded-For entry {} from the right. Ensure exactly {} trusted proxies append to the header, otherwise IP rate limiting is bypassable or misattributed.",
                settings.TRUSTED_PROXY_COUNT,
                settings.TRUSTED_PROXY_COUNT,
                settings.TRUSTED_PROXY_COUNT,
            )

    # Disallow SQLite in production: it's only intended for local development.
    if settings.APP_ENV == "production" and settings.DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Postgres required in production, sqlite is dev-only")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting app in env={} with TRUST_PROXY_HEADERS={}",
        settings.APP_ENV,
        settings.TRUST_PROXY_HEADERS,
    )
    # Validate production-sensitive settings (API key and GitHub token)
    _validate_production_settings(settings)

    logger.info("Startup assumes Alembic migrations have already been applied; run `alembic upgrade head` before starting the app")
    initialize_repo_analysis_concurrency_gate()
    logger.info("Database schema managed by Alembic; application startup continues")
    await resume_pending_repo_analyses()
    yield


app = FastAPI(
    title="Codebase Visualizer API",
    version="0.1.0",
    description="Analyzes GitHub repositories and returns structured dependency graph data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    # Keep the allowed request headers explicit and aligned with the current auth-less flow.
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.exception_handler(RepoNotFoundError)
def handle_repo_not_found(request: Request, exc: RepoNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(RepoPrivateError)
def handle_repo_private(request: Request, exc: RepoPrivateError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(GithubRateLimitError)
def handle_github_rate_limit(request: Request, exc: GithubRateLimitError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(RepoParseError)
def handle_repo_parse(request: Request, exc: RepoParseError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AIServiceError)
def handle_ai_service(request: Request, exc: AIServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0", "env": settings.APP_ENV}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True

    # This endpoint is public, so report only a generic failure. Driver errors can include
    # hostnames and usernames; the full exception goes to the server log instead.
    try:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        logger.exception("Readiness check failed: database")
        healthy = False
        checks["database"] = "error"

    try:
        from app.services.redis_client import get_redis_client

        get_redis_client().ping()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        logger.exception("Readiness check failed: redis")
        healthy = False
        checks["redis"] = "error"

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "unavailable", "checks": checks},
    )


app.include_router(repos_router)
app.include_router(files_router)
