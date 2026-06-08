from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.files import router as files_router
from app.api.routes.repos import router as repos_router
from app.config import settings
from app.database import create_tables
from app.exceptions import (
    AIServiceError,
    GithubRateLimitError,
    RepoNotFoundError,
    RepoParseError,
    RepoPrivateError,
)
from app.logging import get_logger

logger = get_logger(__name__)

@asynccontextmanager
def lifespan(app: FastAPI):
    create_tables()
    logger.info("Database tables ready")
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
    allow_methods=["*"],
    allow_headers=["*"],
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


app.include_router(repos_router)
app.include_router(files_router)
