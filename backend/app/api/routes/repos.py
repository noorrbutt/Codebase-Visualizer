from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

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
from app.exceptions import (
    AIServiceError,
    GithubRateLimitError,
    RepoNotFoundError,
    RepoPrivateError,
)
from app.services.ai import AIService
from app.services.coordination import RedisConcurrencyGate, RedisMutex
from app.services.github import GithubService
from app.services.graph_metrics import compute_graph_metrics
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


def _is_stale(repo: Repository) -> bool:
    if repo.locked_at is None:
        return True

    locked_at = repo.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=timezone.utc)
    stale_after = settings.ANALYSIS_TIMEOUT_SECONDS + 30
    age_seconds = (datetime.now(timezone.utc) - locked_at).total_seconds()
    return age_seconds > stale_after


def _normalize_path_key(file_path: str) -> str:
    path = Path(file_path)
    if path.name == "__init__.py":
        package_key = ".".join(path.parent.parts)
        if package_key:
            return package_key

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


def _resolve_python_relative_import(
    current_path: str, import_path: str, module_map: dict[str, str]
) -> str | None:
    if not import_path.startswith("."):
        return None

    level = len(import_path) - len(import_path.lstrip("."))
    package_parts = PurePosixPath(current_path).parent.parts
    levels_up = level - 1
    if levels_up > len(package_parts):
        return None

    base_parts = package_parts[: len(package_parts) - levels_up] if levels_up else package_parts
    remainder = import_path[level:].replace("/", ".")
    key_parts = (*base_parts, *(remainder.split(".") if remainder else ()))
    key = ".".join(part for part in key_parts if part)
    return module_map.get(key)


def _resolve_python_absolute_import(
    import_path: str, module_map: dict[str, str]
) -> str | None:
    if import_path in module_map and module_map[import_path].endswith(".py"):
        return module_map[import_path]

    matches = {
        path
        for key, path in module_map.items()
        if path.endswith(".py") and key.endswith(f".{import_path}")
    }
    if len(import_path.split(".")) >= 2 or len(matches) == 1:
        return next(iter(matches)) if len(matches) == 1 else None
    return None


def _normalize_import(import_value: str) -> str:
    if import_value.startswith(("./", "../")):
        return import_value
    import_normalized = import_value.replace("/", ".")
    if import_normalized.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".html", ".css", ".md")):
        import_normalized = Path(import_normalized).with_suffix("")
        return ".".join(import_normalized.parts)
    return import_normalized


def _strip_jsonc_comments(content: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False

    while index < len(content):
        char = content[index]
        next_char = content[index + 1] if index + 1 < len(content) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
        elif char == '"':
            in_string = True
            output.append(char)
            index += 1
        elif char == "/" and next_char == "/":
            index += 2
            while index < len(content) and content[index] not in "\r\n":
                index += 1
        elif char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(content) and content[index:index + 2] != "*/":
                index += 1
            index = min(index + 2, len(content))
            output.append(" ")
        else:
            output.append(char)
            index += 1

    uncommented = "".join(output)
    output = []
    index = 0
    in_string = False
    escaped = False
    while index < len(uncommented):
        char = uncommented[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
        elif char == '"':
            in_string = True
            output.append(char)
            index += 1
        elif char == ",":
            next_index = index + 1
            while next_index < len(uncommented) and uncommented[next_index].isspace():
                next_index += 1
            if next_index >= len(uncommented) or uncommented[next_index] not in "}]":
                output.append(char)
            index += 1
        else:
            output.append(char)
            index += 1
    return "".join(output)


def _parse_typescript_aliases(config_text: str | None) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    if not config_text:
        return aliases

    try:
        config = json.loads(_strip_jsonc_comments(config_text))
    except (json.JSONDecodeError, TypeError):
        logger.warning("Ignoring invalid tsconfig/jsconfig JSON")
        return aliases
    if not isinstance(config, dict):
        return aliases

    compiler_options = config.get("compilerOptions")
    if not isinstance(compiler_options, dict):
        return aliases
    base_url_value = compiler_options.get("baseUrl")
    if not isinstance(base_url_value, str):
        base_url = ""
    else:
        base_url = base_url_value.replace("\\", "/").strip("/")
        if base_url.startswith("./"):
            base_url = base_url[2:]
        if base_url == ".":
            base_url = ""

    paths = compiler_options.get("paths")
    if isinstance(paths, dict):
        for pattern, targets in paths.items():
            if not isinstance(pattern, str) or not isinstance(targets, list):
                continue
            resolved_targets = []
            for target in targets:
                if not isinstance(target, str):
                    continue
                normalized_target = target.replace("\\", "/")
                if normalized_target.startswith("./"):
                    normalized_target = normalized_target[2:]
                resolved_targets.append(
                    "/".join(part for part in (base_url, normalized_target) if part)
                )
            if resolved_targets:
                aliases[pattern] = resolved_targets

    if "baseUrl" in compiler_options:
        aliases.setdefault("*", [f"{base_url}/*" if base_url else "*"])
    return aliases


def _resolve_module_candidate(candidate: str, module_map: dict[str, str]) -> str | None:
    normalized = PurePosixPath(candidate.replace("\\", "/"))
    supported_extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md"}
    has_supported_extension = normalized.suffix.lower() in supported_extensions
    key_path = normalized.with_suffix("") if has_supported_extension else normalized
    key = ".".join(key_path.parts)
    if key in module_map:
        return module_map[key]

    if not has_supported_extension:
        for extension in [".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md"]:
            candidate_key = ".".join((*normalized.parts[:-1], normalized.name + extension))
            candidate_key = ".".join(PurePosixPath(candidate_key).with_suffix("").parts)
            if candidate_key in module_map:
                return module_map[candidate_key]

    if normalized.name == "index":
        parent_key = ".".join(normalized.parent.parts)
        if parent_key in module_map:
            return module_map[parent_key]

    return None


def _resolve_alias_import(
    import_value: str,
    aliases: dict[str, list[str]],
    module_map: dict[str, str],
) -> str | None:
    for pattern in sorted(aliases, key=lambda value: (-len(value.replace("*", "")), value)):
        if "*" in pattern:
            prefix, suffix = pattern.split("*", 1)
            if not import_value.startswith(prefix) or not import_value.endswith(suffix):
                continue
            wildcard = import_value[len(prefix):]
            if suffix:
                wildcard = wildcard[:-len(suffix)]
        elif import_value == pattern:
            prefix = pattern
            wildcard = ""
        else:
            continue

        for target in aliases[pattern]:
            candidate = target.replace("*", wildcard, 1)
            resolved = _resolve_module_candidate(candidate, module_map)
            if resolved:
                return resolved
    return None


def _build_edges(
    parsed: dict[str, list[str]], aliases: dict[str, list[str]] | None = None
) -> list[FileEdge]:
    module_map: dict[str, str] = {}
    python_module_map: dict[str, str] = {}

    for path in parsed:
        key = _normalize_path_key(path)
        module_map[key] = path
        if Path(path).suffix.lower() == ".py":
            python_module_map[key] = path

    edges: list[FileEdge] = []
    alias_map = dict(aliases or {})
    if any(path.startswith("src/") for path in parsed):
        alias_map.setdefault("@/*", ["src/*"])

    for source, imports in parsed.items():
        for raw_import in imports:
            if Path(source).suffix.lower() == ".py":
                if raw_import.startswith("."):
                    target_path = _resolve_python_relative_import(
                        source, raw_import, python_module_map
                    )
                else:
                    target_path = _resolve_python_absolute_import(
                        _normalize_import(raw_import), python_module_map
                    )
                if target_path and target_path != source:
                    edges.append(FileEdge(source=source, target=target_path))
                continue

            target_path = (
                None
                if raw_import.startswith((".", ".."))
                else _resolve_alias_import(raw_import, alias_map, module_map)
            )
            if target_path:
                if target_path != source:
                    edges.append(FileEdge(source=source, target=target_path))
                continue

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
            ai_summary_detail=node.ai_summary_detail,
            ai_complexity=node.ai_complexity,
            ai_role=node.ai_role,
        )
        for node in file_nodes
    ]


def _update_repo_analysis_state(
    repo_id: int,
    status: str,
    summary: str | None = None,
    clear_lock: bool = False,
) -> None:
    db = SessionLocal()
    try:
        repo = db.get(Repository, repo_id)
        if repo is None:
            return
        repo.summary = summary
        repo.status = status
        if status == "ready":
            repo.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            repo.error_message = None
            repo.stage = None
        if clear_lock:
            _clear_repo_lock(repo)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _set_repo_analysis_stage(repo_id: int, stage: str) -> None:
    db = SessionLocal()
    try:
        repo = db.get(Repository, repo_id)
        if repo is None:
            return
        repo.stage = stage
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get_or_store_repo_commit_sha(
    repo_id: int, owner: str, repo_name: str, branch: str
) -> str:
    with SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        if repo is None:
            raise RuntimeError(f"Repository {repo_id} disappeared during analysis")
        if repo.commit_sha:
            return repo.commit_sha

    commit_sha = github_service.get_commit_sha(owner, repo_name, branch)
    with SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        if repo is None:
            raise RuntimeError(f"Repository {repo_id} disappeared during analysis")
        if repo.commit_sha is None:
            repo.commit_sha = commit_sha
        db.commit()
        return repo.commit_sha


def _mark_repo_analysis_failed(
    repo_id: int,
    error_message: str = "Analysis failed",
    clear_lock: bool = True,
) -> None:
    db = SessionLocal()
    try:
        repo = db.get(Repository, repo_id)
        if repo is None:
            return
        repo.status = "failed"
        repo.stage = None
        repo.error_message = error_message
        if clear_lock:
            _clear_repo_lock(repo)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _analysis_error_message(exc: Exception) -> str:
    if isinstance(exc, (GithubRateLimitError, RepoNotFoundError, RepoPrivateError)):
        return str(exc)
    return "Analysis failed"


def _fetch_manifest_excerpt(owner: str, repo_name: str, ref: str) -> str | None:
    for path in ("package.json", "pyproject.toml", "requirements.txt"):
        try:
            content = github_service.get_file_content(owner, repo_name, ref, path)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                continue
            logger.warning("Could not fetch {} for {}/{}: {}", path, owner, repo_name, exc)
            return None
        except requests.RequestException as exc:
            logger.warning("Could not fetch {} for {}/{}: {}", path, owner, repo_name, exc)
            return None
        except Exception:
            logger.exception("Could not fetch {} for {}/{}", path, owner, repo_name)
            return None
        return "\n".join(content.splitlines()[:40])
    return None


def _file_is_analyzed(node: FileNode) -> bool:
    return (
        node.analyzed_at is not None
        and node.ai_summary is not None
        and node.ai_summary_detail is not None
        and node.ai_complexity is not None
        and node.ai_role is not None
    )


async def _auto_analyze_top_files(repo_id: int) -> None:
    limit = settings.AUTO_ANALYZE_TOP_FILES
    if limit <= 0:
        return

    try:
        with SessionLocal() as db:
            repo = db.get(Repository, repo_id)
            if repo is None or repo.status != "ready":
                return

            owner = repo.owner
            repo_name = repo.repo_name
            ref = repo.commit_sha or repo.default_branch
            nodes = db.query(FileNode).filter(FileNode.repo_id == repo_id).all()
            edges = db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == repo_id).all()
            node_paths = {node.file_path for node in nodes}
            in_degree = dict.fromkeys(node_paths, 0)
            for edge in edges:
                if edge.target in in_degree:
                    in_degree[edge.target] += 1

            candidates = sorted(
                (node for node in nodes if not _file_is_analyzed(node)),
                key=lambda node: (-in_degree[node.file_path], node.file_path),
            )[:limit]
            candidate_paths = [node.file_path for node in candidates]

        for file_path in candidate_paths:
            with SessionLocal() as db:
                node = (
                    db.query(FileNode)
                    .filter(
                        FileNode.repo_id == repo_id,
                        FileNode.file_path == file_path,
                    )
                    .first()
                )
                if node is None or _file_is_analyzed(node):
                    continue

            try:
                content = await asyncio.to_thread(
                    github_service.get_file_content,
                    owner,
                    repo_name,
                    ref,
                    file_path,
                )
                analysis = await ai_service.analyze_file(
                    file_path,
                    content,
                    client_ip="system:auto",
                )
            except AIServiceError as exc:
                logger.warning(
                    "Stopping automatic file analysis for repo {} at {}: {}",
                    repo_id,
                    file_path,
                    exc,
                )
                break
            except Exception:
                logger.exception(
                    "Automatic file analysis failed for repo {} at {}",
                    repo_id,
                    file_path,
                )
                break

            try:
                with SessionLocal() as db:
                    node = (
                        db.query(FileNode)
                        .filter(
                            FileNode.repo_id == repo_id,
                            FileNode.file_path == file_path,
                        )
                        .first()
                    )
                    if node is None or _file_is_analyzed(node):
                        continue

                    node.ai_summary = analysis["summary"]
                    node.ai_summary_detail = analysis["summary_detail"]
                    node.ai_complexity = analysis["complexity"]
                    node.ai_role = analysis["role"]
                    node.analyzed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.commit()
            except Exception:
                logger.exception(
                    "Failed to save automatic file analysis for repo {} at {}",
                    repo_id,
                    file_path,
                )
                break
    except Exception:
        logger.exception("Automatic file analysis task failed for repo {}", repo_id)


def _persist_repo_analysis_files(
    repo_id: int, node_records: list[FileNode], edges: list[FileEdge]
) -> bool:
    db = SessionLocal()
    try:
        repo = db.get(Repository, repo_id)
        if repo is None:
            return False

        existing_nodes = (
            db.query(FileNode)
            .filter(FileNode.repo_id == repo.id)
            .all()
        )
        ai_data_by_path = {
            node.file_path: (
                node.line_count,
                node.ai_summary,
                node.ai_summary_detail,
                node.ai_complexity,
                node.ai_role,
                node.analyzed_at,
            )
            for node in existing_nodes
        }
        for node in node_records:
            previous = ai_data_by_path.get(node.file_path)
            if previous is not None and previous[0] == node.line_count:
                (
                    _,
                    node.ai_summary,
                    node.ai_summary_detail,
                    node.ai_complexity,
                    node.ai_role,
                    node.analyzed_at,
                ) = previous

        db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == repo.id).delete()
        db.query(FileNode).filter(FileNode.repo_id == repo.id).delete()

        for node in node_records:
            node.repo_id = repo.id
            db.add(node)

        edge_records = [
            FileEdgeModel(repo_id=repo.id, source=edge.source, target=edge.target)
            for edge in edges
        ]
        db.add_all(edge_records)

        repo.total_files = len(node_records)
        repo.status = "parsing"
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _create_repo_analysis_record(
    repo_key: str, owner: str, repo_name: str, branch: str
) -> int:
    db = SessionLocal()
    try:
        existing = db.query(Repository).filter(Repository.github_url == repo_key).first()
        if existing and existing.status == "parsing" and not _is_stale(existing):
            raise HTTPException(
                status_code=409, detail="Repository analysis is already in progress"
            )

        requery = db.query(Repository).filter(Repository.github_url == repo_key).first()
        if requery and requery.status == "parsing" and not _is_stale(requery):
            raise HTTPException(
                status_code=409, detail="Repository analysis is already in progress"
            )

        if requery:
            repo = requery
            repo.repo_name = repo_name
            repo.owner = owner
            repo.default_branch = branch
            repo.commit_sha = None
            repo.status = "parsing"
            repo.stage = None
            repo.error_message = None
        else:
            repo = Repository(
                github_url=repo_key,
                repo_name=repo_name,
                owner=owner,
                default_branch=branch,
                commit_sha=None,
                total_files=0,
                status="parsing",
                stage=None,
                error_message=None,
            )
            db.add(repo)
            try:
                db.flush()
            except IntegrityError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="Repository analysis is already in progress",
                ) from exc

        _claim_repo_lock(repo)
        db.commit()
        return repo.id
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to save repository {}: {}", repo_key, exc)
        raise HTTPException(status_code=500, detail="Failed to persist repository data") from exc
    finally:
        db.close()


def _get_fresh_repo_analysis(repo_key: str, force: bool) -> dict | None:
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.github_url == repo_key).first()
        if repo is None:
            return None
        if repo.status == "parsing" and not _is_stale(repo):
            raise HTTPException(
                status_code=409, detail="Repository analysis is already in progress"
            )
        if repo.status != "ready":
            return None

        updated_at = repo.updated_at or repo.created_at
        if updated_at is None:
            return None
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
        if force and age_seconds >= settings.FORCE_REFRESH_MIN_AGE_SECONDS:
            return None
        if age_seconds >= settings.REPO_CACHE_TTL_SECONDS:
            return None

        return {
            "id": repo.id,
            "repo_name": repo.repo_name,
            "owner": repo.owner,
            "default_branch": repo.default_branch,
            "summary": repo.summary,
        }
    finally:
        db.close()


async def _build_repo_summary(
    repo_id: int,
    repo_name: str,
    file_paths: list[str],
    client_ip: str | None = None,
    readme_excerpt: str | None = None,
    manifest_excerpt: str | None = None,
    top_files: list[str] | None = None,
) -> None:
    try:
        summary = await asyncio.to_thread(
            ai_service.generate_repo_summary,
            repo_name,
            file_paths,
            client_ip=client_ip,
            readme_excerpt=readme_excerpt,
            manifest_excerpt=manifest_excerpt,
            top_files=top_files,
        )
        await asyncio.to_thread(_update_repo_analysis_state, repo_id, "ready", summary)
        logger.info("Repo summary saved for repo {}", repo_id)
    except Exception as exc:
        logger.error("Repo summary background task failed for repo {}: {}", repo_id, exc)
        await asyncio.to_thread(
            _mark_repo_analysis_failed,
            repo_id,
            _analysis_error_message(exc),
            clear_lock=False,
        )


async def _build_repo_analysis(
    repo_id: int,
    owner: str,
    repo_name: str,
    github_url: str,
    branch: str,
    client_ip: str | None = None,
) -> None:
    try:
        logger.info("Starting background analysis for repo {}", repo_id)
        await asyncio.to_thread(_set_repo_analysis_stage, repo_id, "fetching")
        commit_sha = await asyncio.to_thread(
            _get_or_store_repo_commit_sha, repo_id, owner, repo_name, branch
        )
        tree_items = await asyncio.to_thread(
            github_service.get_file_tree, owner, repo_name, commit_sha
        )
        file_paths = [item["path"] for item in tree_items]
        contents = await asyncio.to_thread(
            github_service.fetch_files_concurrent, owner, repo_name, commit_sha, file_paths
        )

        await asyncio.to_thread(_set_repo_analysis_stage, repo_id, "parsing")
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

        typescript_config = await asyncio.to_thread(
            github_service.get_typescript_config, owner, repo_name, commit_sha
        )
        aliases = _parse_typescript_aliases(typescript_config)
        edges = _build_edges(parsed_results, aliases)
        in_degree = dict.fromkeys(parsed_results, 0)
        for edge in edges:
            if edge.target in in_degree:
                in_degree[edge.target] += 1
        top_files = sorted(
            in_degree,
            key=lambda path: (-in_degree[path], path),
        )[:5]
        readme_excerpt = next(
            (
                content[:1500]
                for path, content in contents.items()
                if "/" not in path and path.lower() == "readme.md"
            ),
            None,
        )
        manifest_excerpt = await asyncio.to_thread(
            _fetch_manifest_excerpt, owner, repo_name, commit_sha
        )
        persisted = await asyncio.to_thread(
            _persist_repo_analysis_files, repo_id, node_records, edges
        )
        if not persisted:
            return

        await asyncio.to_thread(_set_repo_analysis_stage, repo_id, "summarizing")
        try:
            summary = await asyncio.to_thread(
                ai_service.generate_repo_summary,
                repo_name,
                file_paths,
                client_ip=client_ip,
                readme_excerpt=readme_excerpt,
                manifest_excerpt=manifest_excerpt,
                top_files=top_files,
            )
            await asyncio.to_thread(
                _update_repo_analysis_state, repo_id, "ready", summary, True
            )
            if settings.AUTO_ANALYZE_TOP_FILES > 0:
                asyncio.create_task(_auto_analyze_top_files(repo_id))
            logger.info("Background repo analysis complete for repo {}", repo_id)
        except AIServiceError as exc:
            await asyncio.to_thread(
                _update_repo_analysis_state, repo_id, "ready", None, True
            )
            logger.warning(
                "AI summary unavailable for repo {} due to budget/AI failure: {}",
                repo_id,
                exc,
            )
            if settings.AUTO_ANALYZE_TOP_FILES > 0:
                asyncio.create_task(_auto_analyze_top_files(repo_id))
            logger.info("Background repo analysis completed without AI summary for repo {}", repo_id)
    except Exception as exc:
        logger.error("Background repo analysis failed for repo {}: {}", repo_id, exc)
        await asyncio.to_thread(
            _mark_repo_analysis_failed,
            repo_id,
            _analysis_error_message(exc),
        )


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
                await asyncio.to_thread(_mark_repo_analysis_failed, repo_id)
                return
        await asyncio.wait_for(
            _build_repo_analysis(repo_id, owner, repo_name, github_url, branch, client_ip=client_ip),
            timeout=settings.ANALYSIS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await asyncio.to_thread(
            _mark_repo_analysis_failed, repo_id, "Analysis timed out"
        )
    except Exception as exc:
        logger.error("Repo analysis task failed for repo {}: {}", repo_id, exc)
        await asyncio.to_thread(
            _mark_repo_analysis_failed,
            repo_id,
            _analysis_error_message(exc),
        )
    finally:
        if slot_preacquired or slot_acquired:
            await release_repo_analysis_slot()


async def resume_pending_repo_analyses() -> None:
    # Try to acquire a global startup reclaim lock so multiple workers
    # don't race to reclaim the same stale repos simultaneously.
    startup_mutex = RedisMutex(key_prefix="startup_reclaim_lock", ttl_seconds=60, redis_client=repo_lock_manager._redis_client)
    token = await startup_mutex.acquire("reclaim", timeout=0)
    if token is None:
        # Another worker is already reclaiming; skip.
        logger.info("Startup reclaim skipped because another worker holds the startup_reclaim_lock")
        return

    db = SessionLocal()
    try:
        pending_repos = db.query(Repository).filter(Repository.status == "parsing").all()
        reclaimed = 0
        skipped = 0
        worker_id = uuid.uuid4().hex

        for repo in pending_repos:
            rows = (
                db.query(Repository)
                .filter(Repository.id == repo.id, Repository.status == "parsing")
                .update(
                    {
                        Repository.locked_at: datetime.now(timezone.utc),
                        Repository.worker_id: worker_id,
                        Repository.commit_sha: None,
                        Repository.stage: None,
                        Repository.error_message: None,
                    },
                    synchronize_session=False,
                )
            )
            if rows:
                db.commit()
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        _build_repo_analysis_with_timeout(
                            repo.id,
                            repo.owner,
                            repo.repo_name,
                            repo.github_url,
                            repo.default_branch,
                        )
                    )
                except RuntimeError:
                    logger.error(
                        "resume_pending_repo_analyses called outside running loop, skipping - repo %s left for another worker to reclaim",
                        repo.id,
                    )
                    # leave the claim so another worker may reclaim later
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
        await startup_mutex.release("reclaim", token)


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(_require_api_key)])
async def analyze_repo(
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
) -> AnalyzeResponse:
    client_ip = IPRateLimiter.resolve_client_ip(request)
    if not await asyncio.to_thread(repo_rate_limiter.allow, client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded for repository analysis")

    owner, repo_name = github_service.parse_repo_url(str(payload.github_url))
    repo_key = f"https://github.com/{owner}/{repo_name}".lower()
    lock_token = await repo_lock_manager.acquire(repo_key)
    if lock_token is None:
        raise HTTPException(
            status_code=409, detail="Repository analysis is already in progress"
        )

    slot_acquired = False
    try:
        cached_repo = await asyncio.to_thread(
            _get_fresh_repo_analysis, repo_key, payload.force
        )
        if cached_repo is not None:
            return AnalyzeResponse(
                **cached_repo,
                status="ready",
                nodes=[],
                edges=[],
            )

        metadata = await asyncio.to_thread(
            github_service.get_repo_metadata, owner, repo_name
        )
        full_name = metadata.get("full_name")
        if isinstance(full_name, str) and "/" in full_name:
            owner, repo_name = full_name.split("/", 1)
        branch = metadata.get("default_branch", "main")

        slot_acquired = await acquire_repo_analysis_slot()
        if not slot_acquired:
            raise HTTPException(
                status_code=503,
                detail="Too many repository analyses are currently running",
            )

        repo_id = await asyncio.to_thread(
            _create_repo_analysis_record, repo_key, owner, repo_name, branch
        )

        try:
            background_tasks.add_task(
                _build_repo_analysis_with_timeout,
                repo_id,
                owner,
                repo_name,
                repo_key,
                branch,
                True,
                client_ip,
            )
        except Exception as exc:
            await release_repo_analysis_slot()
            slot_acquired = False
            await asyncio.to_thread(
                _mark_repo_analysis_failed, repo_id, "Analysis failed"
            )
            logger.error(
                "Saved repository %s but failed to queue analysis: %s", repo_key, exc
            )
            raise HTTPException(
                status_code=500, detail="Repository saved but analysis scheduling failed"
            )

        response = AnalyzeResponse(
            id=repo_id,
            repo_name=repo_name,
            owner=owner,
            default_branch=branch,
            status="parsing",
            summary=None,
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


@router.get("/{repo_id}/status", dependencies=[Depends(_require_api_key)])
def get_repo_status(repo_id: int, db: Session = Depends(get_db)) -> dict[str, str | None]:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {"status": repo.status, "error": repo.error_message, "stage": repo.stage}


@router.get("/", response_model=list[RepoListItem], dependencies=[Depends(_require_api_key)])
def list_repos(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[RepoListItem]:
    query = db.query(Repository)
    if status is not None:
        query = query.filter(Repository.status == status)
    repos = (
        query.order_by(Repository.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
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


@router.get(
    "/by-name/{owner}/{repo}",
    response_model=AnalyzeResponse,
    dependencies=[Depends(_require_api_key)],
)
def get_repo_by_name(owner: str, repo: str, db: Session = Depends(get_db)) -> AnalyzeResponse:
    record = (
        db.query(Repository)
        .filter(
            func.lower(Repository.owner) == owner.lower(),
            func.lower(Repository.repo_name) == repo.lower(),
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    nodes = db.query(FileNode).filter(FileNode.repo_id == record.id).all()
    edges = db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == record.id).all()
    node_records = _normalize_file_records(nodes)
    return AnalyzeResponse(
        id=record.id,
        repo_name=record.repo_name,
        owner=record.owner,
        default_branch=record.default_branch,
        status=record.status,
        summary=record.summary,
        nodes=node_records,
        edges=edges,
        metrics=compute_graph_metrics(
            (node.path for node in node_records),
            ({"source": edge.source, "target": edge.target} for edge in edges),
        ),
    )


@router.get("/{repo_id}", response_model=AnalyzeResponse, dependencies=[Depends(_require_api_key)])
def get_repo(repo_id: int, db: Session = Depends(get_db)) -> AnalyzeResponse:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    nodes = db.query(FileNode).filter(FileNode.repo_id == repo_id).all()
    edges = db.query(FileEdgeModel).filter(FileEdgeModel.repo_id == repo_id).all()
    node_records = _normalize_file_records(nodes)

    return AnalyzeResponse(
        id=repo.id,
        repo_name=repo.repo_name,
        owner=repo.owner,
        default_branch=repo.default_branch,
        status=repo.status,
        summary=repo.summary,
        nodes=node_records,
        edges=edges,
        metrics=compute_graph_metrics(
            (node.path for node in node_records),
            ({"source": edge.source, "target": edge.target} for edge in edges),
        ),
    )