from __future__ import annotations

import asyncio
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.file_edge import FileEdge as FileEdgeModel
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.schemas.repository import AnalyzeResponse, AnalyzeRequest, FileEdge, FileNodeOut, RepoListItem
from app.services.ai import AIService
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
repo_rate_limiter = IPRateLimiter(max_requests=settings.RATE_LIMIT_REQUESTS_PER_MINUTE, window_seconds=60)


def _normalize_path_key(file_path: str) -> str:
    normalized = Path(file_path).with_suffix("")
    key = ".".join(normalized.parts)
    if key.endswith(".index"):
        return key[: -len(".index")]
    return key


def _resolve_relative_import(current_path: str, import_path: str, module_map: dict[str, str]) -> str | None:
    if not import_path.startswith(('.', '..')):
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
    if import_value.startswith(('./', '../')):
        return import_value
    import_normalized = import_value.replace('/', '.')
    if import_normalized.endswith(('.js', '.jsx', '.ts', '.tsx', '.py', '.html', '.css', '.md')):
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


async def _build_repo_summary(repo_id: int, repo_name: str, file_paths: list[str]) -> None:
    db = SessionLocal()
    try:
        summary = await asyncio.to_thread(ai_service.generate_repo_summary, repo_name, file_paths)
        repo = db.get(Repository, repo_id)
        if repo is None:
            return

        repo.summary = summary
        repo.status = "ready"
        db.commit()
        logger.info("Repo summary saved for repo %s", repo_id)
    except Exception as exc:
        db.rollback()
        logger.error("Repo summary background task failed for repo %s: %s", repo_id, exc)
        repo = db.get(Repository, repo_id)
        if repo:
            repo.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_repo(
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    request: Request = None,
) -> AnalyzeResponse:
    client_ip = request.client.host if request and request.client else "unknown"
    if not repo_rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for repository analysis")
    owner, repo_name = github_service.parse_repo_url(str(payload.github_url))
    metadata = github_service.get_repo_metadata(owner, repo_name)
    branch = metadata.get("default_branch", "main")
    tree_items = github_service.get_file_tree(owner, repo_name, branch)
    file_paths = [item["path"] for item in tree_items]
    contents = github_service.fetch_files_concurrent(owner, repo_name, branch, file_paths)

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

    repo = Repository(
        github_url=str(payload.github_url),
        repo_name=repo_name,
        owner=owner,
        default_branch=branch,
        total_files=len(node_records),
        status="parsing",
    )

    try:
        existing = db.query(Repository).filter(Repository.github_url == str(payload.github_url)).first()
        if existing:
            db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == existing.id).delete()
            db.query(FileNode).filter(FileNode.repo_id == existing.id).delete()
            db.delete(existing)
            db.flush()

        db.add(repo)
        db.flush()

        for node in node_records:
            node.repo_id = repo.id
            db.add(node)

        edges = _build_edges(parsed_results)
        edge_records = [
            FileEdgeModel(repo_id=repo.id, source=edge.source, target=edge.target)
            for edge in edges
        ]
        for edge_record in edge_records:
            db.add(edge_record)

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save repository %s: %s", payload.github_url, exc)
        raise HTTPException(status_code=500, detail="Failed to persist repository data")

    background_tasks.add_task(_build_repo_summary, repo.id, repo_name, file_paths)

    response = AnalyzeResponse(
        id=repo.id,
        repo_name=repo.repo_name,
        owner=repo.owner,
        default_branch=repo.default_branch,
        status=repo.status,
        summary=repo.summary,
        nodes=_normalize_file_records(node_records),
        edges=edges,
    )
    return response


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