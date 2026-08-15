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

    # Warn when trusting X-Forwarded-For headers in production. This should
    # only be enabled when a trusted reverse proxy strips client-supplied
    # values; otherwise IP-based rate limits are trivially bypassed.
    if settings.TRUST_PROXY_HEADERS and settings.APP_ENV == "production":
        logger.warning(
            "TRUST_PROXY_HEADERS=True - ensure a trusted reverse proxy strips client-supplied X-Forwarded-For before requests reach this app, otherwise IP rate limiting is trivially bypassed"
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

    try:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["database"] = f"error: {exc}"

    try:
        from app.services.redis_client import get_redis_client

        get_redis_client().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["redis"] = f"error: {exc}"

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "unavailable", "checks": checks},
    )


app.include_router(repos_router)
app.include_router(files_router)
