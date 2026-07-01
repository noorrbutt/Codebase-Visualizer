from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AIServiceError
from app.config import settings
from app.logging import get_logger
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.schemas.file_node import FileAnalyzeRequest, FileAnalyzeResponse
from app.services.ai import AIService
from app.services.github import GithubService
from app.services.rate_limit import IPRateLimiter

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

github_service = GithubService()
ai_service = AIService()
file_rate_limiter = IPRateLimiter(max_requests=settings.RATE_LIMIT_REQUESTS_PER_MINUTE, window_seconds=60)


@router.post("/analyze", response_model=FileAnalyzeResponse)
async def analyze_file(
    payload: FileAnalyzeRequest,
    db: Session = Depends(get_db),
    request: Request = None,
) -> FileAnalyzeResponse:
    client_ip = request.client.host if request and request.client else "unknown"
    if not file_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for file analysis")
    node = (
        db.query(FileNode)
        .filter(FileNode.repo_id == payload.repo_id, FileNode.file_path == payload.file_path)
        .first()
    )
    if node is None:
        raise HTTPException(status_code=404, detail="File node not found")

    if node.analyzed_at is not None and node.ai_summary is not None and node.ai_complexity is not None and node.ai_role is not None:
        return FileAnalyzeResponse(
            file_path=node.file_path,
            ai_summary=node.ai_summary,
            ai_complexity=node.ai_complexity,
            ai_role=node.ai_role,
        )

    repo = db.query(Repository).filter(Repository.id == payload.repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    content = github_service.get_file_content(repo.owner, repo.repo_name, repo.default_branch, node.file_path)
    try:
        analysis = await ai_service.analyze_file(node.file_path, content)
    except AIServiceError as exc:
        logger.warning("AI analysis unavailable for %s/%s: %s", repo.github_url, node.file_path, exc)
        raise HTTPException(
            status_code=503,
            detail="AI analysis temporarily unavailable. Try again in a few seconds.",
        )

    try:
        node.ai_summary = analysis["summary"]
        node.ai_complexity = analysis["complexity"]
        node.ai_role = analysis["role"]
        node.analyzed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update analysis for %s/%s: %s", repo.github_url, node.file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to persist file analysis")

    return FileAnalyzeResponse(
        file_path=node.file_path,
        ai_summary=node.ai_summary,
        ai_complexity=node.ai_complexity,
        ai_role=node.ai_role,
    )
