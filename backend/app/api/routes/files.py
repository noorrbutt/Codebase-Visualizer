from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AIServiceError
from app.logging import get_logger
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.schemas.file_node import FileAnalyzeRequest, FileAnalyzeResponse
from app.services.ai import AIService
from app.services.github import GithubService

logger = get_logger(__name__)
router = APIRouter(prefix="/files", tags=["files"])

github_service = GithubService()
ai_service = AIService()


@router.post("/analyze", response_model=FileAnalyzeResponse)
def analyze_file(request: FileAnalyzeRequest, db: Session = Depends(get_db)) -> FileAnalyzeResponse:
    node = (
        db.query(FileNode)
        .filter(FileNode.repo_id == request.repo_id, FileNode.file_path == request.file_path)
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

    repo = db.query(Repository).filter(Repository.id == request.repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    content = github_service.get_file_content(repo.owner, repo.repo_name, repo.default_branch, node.file_path)
    try:
        analysis = ai_service.analyze_file(node.file_path, content)
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
