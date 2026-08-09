from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import _require_api_key
from app.database import SessionLocal, get_db
from app.models.file_edge import FileEdge as FileEdgeModel
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.schemas.repository import (
    AnalyzeResponse,
    AnalyzeRequest,
    FileEdge,
    FileNodeOut,
    RepoListItem,
)
from app.services.ai import AIService
from app.services.coordination import RedisConcurrencyGate, RedisMutex
from app.services.github import GithubService
from app.services.parser import CodeParser
from app.services.rate_limit import IPRateLimiter
from app.logging import get_logger
from app.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/repos", tags=["repositories"])


github_service = GithubService()
code_parser = CodeParser()
ai_service = AIService()
repo_rate_limiter = IPRateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS_PER_MINUTE, window_seconds=60
)
# Both structures below are Redis-backed (see app/services/coordination.py) so
# the concurrency cap and per-repo locking hold across process restarts and
# multiple instances, not just within one running process.
repo_analysis_concurrency_gate: RedisConcurrencyGate | None = None
repo_lock_manager = RedisMutex(key_prefix="repo_lock", ttl_seconds=settings.RECLAIM_LOCK_AFTER_SECONDS)


def initialize_repo_analysis_concurrency_gate(limit: int | None = None) -> RedisConcurrencyGate:
    global repo_analysis_concurrency_gate
    effective_limit = limit if limit is not None else settings.MAX_CONCURRENT_REPO_ANALYSES
    if repo_analysis_concurrency_gate is None or repo_analysis_concurrency_gate._max_concurrent_analyses != effective_limit:
        repo_analysis_concurrency_gate = RedisConcurrencyGate(effective_limit)
    return repo_analysis_concurrency_gate
# Tests inject a fake Redis client by monkeypatching repo_analysis_concurrency_gate
# and repo_lock_manager directly (see tests/test_repos.py), the same way
# tests/test_protection_limits.py injects one into IPRateLimiter/AIService.


async def acquire_repo_analysis_slot() -> bool:
    return await initialize_repo_analysis_concurrency_gate().try_acquire()


async def release_repo_analysis_slot() -> None:
    if repo_analysis_concurrency_gate is not None:
        await repo_analysis_concurrency_gate.release()


def _claim_repo_lock(repo: Repository) -> None:
    repo.locked_at = datetime.now(timezone.utc)
    repo.worker_id = uuid.uuid4().hex


def _clear_repo_lock(repo: Repository | None) -> None:
    if repo is None:
        return
    repo.locked_at = None
    repo.worker_id = None


def _normalize_path_key(file_path: str) -> str:
    normalized = Path(file_path).with_suffix("")
    key = ".".join(normalized.parts)
    if key.endswith(".index"):
        return key[: -len(".index")]
    return key


def _resolve_relative_import(
    current_path: str, import_path: str, module_map: dict[str, str]
) -> str | None:
    if not import_path.startswith((".", "..")):
        return None

    base_dir = Path(current_path).parent
    candidate = PurePosixPath(base_dir.as_posix()).joinpath(import_path)
    normalized_parts: list[str] = []

    for part in candidate.parts:
        if part == ".":
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)

    resolved = PurePosixPath(*normalized_parts)
    key = ".".join(resolved.with_suffix("").parts)
    if key in module_map:
        return module_map[key]

    for extension in [".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md"]:
        candidate_key = ".".join(resolved.with_suffix(extension).with_suffix("").parts)
        if candidate_key in module_map:
            return module_map[candidate_key]

    if resolved.name == "index":
        parent_key = ".".join(resolved.parent.parts)
        if parent_key in module_map:
            return module_map[parent_key]

    return None


def _normalize_import(import_value: str) -> str:
    if import_value.startswith(("./", "../")):
        return import_value
    import_normalized = import_value.replace("/", ".")
    if import_normalized.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".html", ".css", ".md")):
        import_normalized = Path(import_normalized).with_suffix("")
        return ".".join(import_normalized.parts)
    return import_normalized


def _build_edges(parsed: dict[str, list[str]]) -> list[FileEdge]:
    module_map: dict[str, str] = {}

    for path in parsed:
        key = _normalize_path_key(path)
        module_map[key] = path

    edges: list[FileEdge] = []

    for source, imports in parsed.items():
        for raw_import in imports:
            normalized_import = _normalize_import(raw_import)
            target_path = module_map.get(normalized_import)

            if not target_path:
                target_path = _resolve_relative_import(source, raw_import, module_map)

            if target_path and target_path != source:
                edges.append(FileEdge(source=source, target=target_path))

    return edges


def _normalize_file_records(file_nodes: list[FileNode]) -> list[FileNodeOut]:
    return [
        FileNodeOut(
            id=node.id,
            path=node.file_path,
            language=node.language,
            line_count=node.line_count,
            import_count=node.import_count,
            ai_summary=node.ai_summary,
            ai_complexity=node.ai_complexity,
            ai_role=node.ai_role,
        )
        for node in file_nodes
    ]


async def _build_repo_summary(
    repo_id: int,
    repo_name: str,
    file_paths: list[str],
    client_ip: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        summary = await asyncio.to_thread(
            ai_service.generate_repo_summary,
            repo_name,
            file_paths,
            client_ip=client_ip,
        )
        repo = db.get(Repository, repo_id)
        if repo is None:
            return

        repo.summary = summary
        repo.status = "ready"
        db.commit()
        logger.info("Repo summary saved for repo {}", repo_id)
    except Exception as exc:
        db.rollback()
        logger.error("Repo summary background task failed for repo {}: {}", repo_id, exc)
        repo = db.get(Repository, repo_id)
        if repo:
            repo.status = "failed"
            db.commit()
    finally:
        db.close()


async def _build_repo_analysis(
    repo_id: int,
    owner: str,
    repo_name: str,
    github_url: str,
    branch: str,
    client_ip: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        logger.info("Starting background analysis for repo {}", repo_id)
        tree_items = await asyncio.to_thread(github_service.get_file_tree, owner, repo_name, branch)
        file_paths = [item["path"] for item in tree_items]
        contents = await asyncio.to_thread(
            github_service.fetch_files_concurrent, owner, repo_name, branch, file_paths
        )

        parsed_results: dict[str, list[str]] = {}
        node_records: list[FileNode] = []

        for path, content in contents.items():
            result = code_parser.parse(path, content)
            parsed_results[path] = result["imports"]
            node_records.append(
                FileNode(
                    file_path=path,
                    language=result["language"],
                    line_count=result["line_count"],
                    import_count=len(result["imports"]),
                )
            )

        repo = db.get(Repository, repo_id)
        if repo is None:
            return

        db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == repo.id).delete()
        db.query(FileNode).filter(FileNode.repo_id == repo.id).delete()

        for node in node_records:
            node.repo_id = repo.id
            db.add(node)

        edges = _build_edges(parsed_results)
        edge_records = [
            FileEdgeModel(repo_id=repo.id, source=edge.source, target=edge.target) for edge in edges
        ]
        for edge_record in edge_records:
            db.add(edge_record)

        repo.total_files = len(node_records)
        repo.status = "parsing"
        db.commit()

        summary = await asyncio.to_thread(
            ai_service.generate_repo_summary,
            repo_name,
            file_paths,
            client_ip=client_ip,
        )
        repo.summary = summary
        repo.status = "ready"
        # clear any claim information now that analysis completed
        _clear_repo_lock(repo)
        db.commit()
        logger.info("Background repo analysis complete for repo {}", repo_id)
    except Exception as exc:
        db.rollback()
        logger.error("Background repo analysis failed for repo {}: {}", repo_id, exc)
        repo = db.get(Repository, repo_id)
        if repo:
            repo.status = "failed"
            _clear_repo_lock(repo)
            db.commit()
    finally:
        db.close()


async def _build_repo_analysis_with_timeout(
    repo_id: int,
    owner: str,
    repo_name: str,
    github_url: str,
    branch: str,
    slot_preacquired: bool = False,
    client_ip: str | None = None,
) -> None:
    slot_acquired = False
    try:
        # Lifecycle order must remain stable across both coordination layers:
        #   1) repo lock row is claimed in analyze_repo() before the background task is queued
        #   2) the global analysis slot is acquired in this helper (or pre-acquired by the request)
        #   3) background work is executed
        #   4) the global slot is released in finally after work completes
        #   5) the repo lock row is cleared by _build_repo_analysis() once the worker finishes or fails
        if not slot_preacquired:
            slot_acquired = await acquire_repo_analysis_slot()
            if not slot_acquired:
                logger.info("Skipping repo analysis {} because the concurrent cap is already reached", repo_id)
                db = SessionLocal()
                try:
                    repo = db.get(Repository, repo_id)
                    if repo is not None:
                        repo.status = "failed"
                        _clear_repo_lock(repo)
                        db.commit()
                finally:
                    db.close()
                return
        await asyncio.wait_for(
            _build_repo_analysis(repo_id, owner, repo_name, github_url, branch, client_ip=client_ip),
            timeout=120,
        )
    except asyncio.TimeoutError:
        db = SessionLocal()
        try:
            repo = db.get(Repository, repo_id)
            if repo is not None:
                repo.status = "failed"
                _clear_repo_lock(repo)
                db.commit()
        finally:
            db.close()
    finally:
        if slot_preacquired or slot_acquired:
            await release_repo_analysis_slot()


def resume_pending_repo_analyses() -> None:
    db = SessionLocal()
    try:
        pending_repos = db.query(Repository).filter(Repository.status == "parsing").all()
        reclaimed = 0
        skipped = 0
        worker_id = uuid.uuid4().hex
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.RECLAIM_LOCK_AFTER_SECONDS)

        for repo in pending_repos:
            rows = (
                db.query(Repository)
                .filter(Repository.id == repo.id, Repository.status == "parsing")
                .filter((Repository.locked_at.is_(None)) | (Repository.locked_at < cutoff))
                .update(
                        {Repository.locked_at: datetime.now(timezone.utc), Repository.worker_id: worker_id},                    synchronize_session=False,
                )
            )
            if rows:
                db.commit()
                try:
                    asyncio.get_running_loop().create_task(
                        _build_repo_analysis_with_timeout(
                            repo.id,
                            repo.owner,
                            repo.repo_name,
                            repo.github_url,
                            repo.default_branch,
                        )
                    )
                except RuntimeError:
                    # fallback if called outside of a running loop
                    try:
                        asyncio.get_event_loop().create_task(
                            _build_repo_analysis_with_timeout(
                                repo.id,
                                repo.owner,
                                repo.repo_name,
                                repo.github_url,
                                repo.default_branch,
                            )
                        )
                    except Exception:
                        logger.exception("Failed to schedule reclaimed repo %s", repo.id)
                        # leave the claim so another startup may reclaim later
                        skipped += 1
                        continue

                reclaimed += 1
                logger.info("Rescheduled pending analysis for repo {} (reclaimed)", repo.id)
            else:
                skipped += 1
                logger.info("Skipped pending repo {} — currently locked by another worker", repo.id)

        logger.info("Resume pending analyses summary: reclaimed={} skipped={}", reclaimed, skipped)
    finally:
        db.close()


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(_require_api_key)])
async def analyze_repo(
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    request: Request = None,
) -> AnalyzeResponse:
    client_ip = IPRateLimiter.resolve_client_ip(request)
    if not repo_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for repository analysis")

    repo_key = str(payload.github_url)
    lock_token = await repo_lock_manager.acquire(repo_key)
    if lock_token is None:
        raise HTTPException(
            status_code=409, detail="Repository analysis is already in progress"
        )

    slot_acquired = False
    try:
        owner, repo_name = github_service.parse_repo_url(repo_key)
        metadata = github_service.get_repo_metadata(owner, repo_name)
        branch = metadata.get("default_branch", "main")

        existing = db.query(Repository).filter(Repository.github_url == repo_key).first()
        if existing and existing.status == "parsing":
            raise HTTPException(status_code=409, detail="Repository analysis is already in progress")

        repo = Repository(
            github_url=repo_key,
            repo_name=repo_name,
            owner=owner,
            default_branch=branch,
            total_files=0,
            status="parsing",
        )

        try:
            if existing:
                db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == existing.id).delete()
                db.query(FileNode).filter(FileNode.repo_id == existing.id).delete()
                db.delete(existing)
                db.flush()

            db.add(repo)
            db.flush()

            # Claim the repo row before the global slot is checked so the repo-specific
            # lock is the first coordination primitive to be taken.
            _claim_repo_lock(repo)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save repository {}: {}", repo_key, exc)
            raise HTTPException(status_code=500, detail="Failed to persist repository data")

        slot_acquired = await acquire_repo_analysis_slot()
        if not slot_acquired:
            db.delete(repo)
            db.commit()
            raise HTTPException(
                status_code=503,
                detail="Too many repository analyses are currently running",
            )

        try:
            background_tasks.add_task(
                _build_repo_analysis_with_timeout,
                repo.id,
                owner,
                repo_name,
                repo_key,
                branch,
                True,
                client_ip,
            )
        except Exception as exc:
            await release_repo_analysis_slot()
            db.delete(repo)
            db.commit()
            logger.error(
                "Saved repository %s but failed to queue analysis: %s", repo_key, exc
            )
            raise HTTPException(
                status_code=500, detail="Repository saved but analysis scheduling failed"
            )

        response = AnalyzeResponse(
            id=repo.id,
            repo_name=repo.repo_name,
            owner=repo.owner,
            default_branch=repo.default_branch,
            status=repo.status,
            summary=repo.summary,
            nodes=[],
            edges=[],
        )
        return response
    except Exception:
        if slot_acquired:
            await release_repo_analysis_slot()
        raise
    finally:
        await repo_lock_manager.release(repo_key, lock_token)


@router.get("/{repo_id}/status")
def get_repo_status(repo_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"status": repo.status}


@router.get("/", response_model=list[RepoListItem])
def list_repos(db: Session = Depends(get_db)) -> list[RepoListItem]:
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    return [
        RepoListItem(
            id=repo.id,
            repo_name=repo.repo_name,
            owner=repo.owner,
            github_url=repo.github_url,
            status=repo.status,
            total_files=repo.total_files,
            created_at=repo.created_at,
        )
        for repo in repos
    ]


@router.get("/{repo_id}", response_model=AnalyzeResponse)
def get_repo(repo_id: int, db: Session = Depends(get_db)) -> AnalyzeResponse:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    nodes = db.query(FileNode).filter(FileNode.repo_id == repo_id).all()
    edges = db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == repo_id).all()

    return AnalyzeResponse(
        id=repo.id,
        repo_name=repo.repo_name,
        owner=repo.owner,
        default_branch=repo.default_branch,
        status=repo.status,
        summary=repo.summary,
        nodes=_normalize_file_records(nodes),
        edges=edges,
    )