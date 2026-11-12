from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.routes.repos as repos_module
import app.api.routes.files as files_module
import app.database as database_module
import app.main as main_module
import app.services.rate_limit as rate_limit_module
from app.database import Base
from app.exceptions import (
    AIBudgetExceededError,
    AIServiceError,
    GithubRateLimitError,
    RepoNotFoundError,
    RepoPrivateError,
)
from app.models.file_edge import FileEdge
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.main import app
from app.services.coordination import RedisConcurrencyGate, RedisMutex
from tests.conftest import InMemoryRedis


# Fake startup mutex used in reclaim tests to allow reclaim to proceed
class FakeStartupMutex:
    def __init__(self, *args, **kwargs):
        pass

    async def acquire(self, name, timeout=0, poll_interval=0.2):
        return "token"

    async def release(self, name, token):
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_module, "create_tables", lambda: Base.metadata.create_all(bind=engine))
    monkeypatch.setattr(main_module.settings, "API_KEY", "test-api-key")
    monkeypatch.setattr(repos_module.settings, "API_KEY", "test-api-key")
    monkeypatch.setattr(repos_module.github_service, "get_typescript_config", lambda *args: None)

    # Coordination (concurrency gate + per-repo mutex) is Redis-backed in
    # production; swap in the same in-memory fake used elsewhere in this
    # suite so tests don't need a real Redis server.
    fake_redis = InMemoryRedis()
    monkeypatch.setattr(
        repos_module,
        "repo_analysis_concurrency_gate",
        RedisConcurrencyGate(repos_module.settings.MAX_CONCURRENT_REPO_ANALYSES, redis_client=fake_redis),
    )
    monkeypatch.setattr(
        repos_module,
        "repo_lock_manager",
        RedisMutex(
            key_prefix="repo_lock",
            ttl_seconds=repos_module.settings.RECLAIM_LOCK_AFTER_SECONDS,
            redis_client=fake_redis,
        ),
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client


def test_cors_allows_configured_frontend_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_repo_status_includes_error_message(client):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="failed",
            stage=None,
            error_message="Repository not found: https://github.com/octocat/hello-world",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    response = client.get(
        f"/repos/{repo_id}/status", headers={"X-API-Key": "test-api-key"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "error": "Repository not found: https://github.com/octocat/hello-world",
        "stage": None,
    }


def test_slow_github_metadata_does_not_block_health(client, monkeypatch):
    metadata_started = threading.Event()

    def slow_get_repo_metadata(owner, repo_name):
        metadata_started.set()
        time.sleep(0.5)
        return {"default_branch": "main"}

    async def skip_repo_analysis(*args, **kwargs):
        return None

    monkeypatch.setattr(
        repos_module.github_service,
        "parse_repo_url",
        lambda url: ("octocat", "hello-world"),
    )
    monkeypatch.setattr(
        repos_module.github_service, "get_repo_metadata", slow_get_repo_metadata
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", skip_repo_analysis
    )

    async def make_requests():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            analyze_task = asyncio.create_task(
                async_client.post(
                    "/repos/analyze",
                    json={"github_url": "https://github.com/octocat/hello-world"},
                    headers={"X-API-Key": "test-api-key"},
                )
            )
            assert await asyncio.to_thread(metadata_started.wait, 1)
            started_at = asyncio.get_running_loop().time()
            health_response = await async_client.get("/health")
            health_duration = asyncio.get_running_loop().time() - started_at
            analyze_response = await analyze_task
            return health_response, health_duration, analyze_response

    health_response, health_duration, analyze_response = asyncio.run(make_requests())

    assert health_response.status_code == 200
    assert health_duration < 0.2
    assert analyze_response.status_code == 200


def test_cors_allows_x_api_key_header_for_analyze(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"Origin": "http://localhost:5173", "X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_analyze_status_and_detail_flow(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    body = response.json()
    repo_id = body["id"]

    with database_module.SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        assert repo is not None
        repo.status = "ready"
        repo.summary = "summary"
        db.add(
            FileNode(
                repo_id=repo_id,
                file_path="src/app.py",
                language="python",
                line_count=1,
                import_count=0,
            )
        )
        db.add(FileEdge(repo_id=repo_id, source="src/app.py", target="src/utils.py"))
        db.commit()

    status_response = client.get(f"/repos/{repo_id}/status", headers={"X-API-Key": "test-api-key"})
    detail_response = client.get(f"/repos/{repo_id}", headers={"X-API-Key": "test-api-key"})

    assert status_response.status_code == 200
    assert status_response.json() == {"status": "ready", "error": None, "stage": None}
    assert detail_response.status_code == 200
    assert detail_response.json()["nodes"][0]["path"] == "src/app.py"
    assert detail_response.json()["edges"][0]["source"] == "src/app.py"
    assert detail_response.json()["metrics"]["top_fan_out"] == [
        {"path": "src/app.py", "count": 1}
    ]


def test_get_repo_by_name_is_case_insensitive_and_returns_graph(client):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="OctoCat",
            repo_name="Hello-World",
            github_url="https://github.com/OctoCat/Hello-World",
            default_branch="main",
            status="ready",
            summary="summary",
        )
        db.add(repo)
        db.flush()
        db.add(
            FileNode(
                repo_id=repo.id,
                file_path="src/app.py",
                language="python",
                line_count=1,
                import_count=0,
            )
        )
        db.add(FileEdge(repo_id=repo.id, source="src/app.py", target="src/utils.py"))
        db.commit()
        repo_id = repo.id

    response = client.get(
        "/repos/by-name/oCtOcAt/hElLo-WoRlD",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == repo_id
    assert response.json()["summary"] == "summary"
    assert response.json()["nodes"][0]["path"] == "src/app.py"
    assert response.json()["edges"][0]["target"] == "src/utils.py"
    assert response.json()["metrics"]["top_fan_out"] == [
        {"path": "src/app.py", "count": 1}
    ]


def test_get_repo_by_name_returns_404_when_missing(client):
    response = client.get(
        "/repos/by-name/octocat/missing",
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 404


def test_analyze_reuses_ready_repo_within_cache_ttl(client, monkeypatch):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="ready",
            summary="cached summary",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    def unexpected_call(*args, **kwargs):
        raise AssertionError("fresh cache should not call GitHub or schedule analysis")

    monkeypatch.setattr(
        repos_module.github_service, "get_repo_metadata", unexpected_call
    )
    monkeypatch.setattr(repos_module.github_service, "get_file_tree", unexpected_call)
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == repo_id
    assert response.json()["status"] == "ready"
    assert response.json()["summary"] == "cached summary"

    with database_module.SessionLocal() as db:
        repos = db.query(Repository).all()
        assert len(repos) == 1
        assert repos[0].status == "ready"


def test_force_analyze_reuses_repository_row_and_schedules_rebuild(client, monkeypatch):
    old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=600)
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="ready",
            error_message="old error",
            created_at=old_timestamp,
            updated_at=old_timestamp,
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    metadata_calls = []
    scheduled = []
    monkeypatch.setattr(
        repos_module.github_service,
        "parse_repo_url",
        lambda url: ("octocat", "hello-world"),
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, name: metadata_calls.append((owner, name))
        or {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)

    async def record_rebuild(*args, **kwargs):
        scheduled.append(args[0])

    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", record_rebuild
    )

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world", "force": True},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == repo_id
    assert response.json()["status"] == "parsing"
    assert metadata_calls == [("octocat", "hello-world")]
    assert scheduled == [repo_id]

    with database_module.SessionLocal() as db:
        repos = db.query(Repository).all()
        assert len(repos) == 1
        assert repos[0].id == repo_id
        assert repos[0].status == "parsing"
        assert repos[0].error_message is None


def test_force_analyze_reuses_repository_younger_than_force_refresh_cooldown(
    client, monkeypatch
):
    recent_timestamp = datetime.now(timezone.utc) - timedelta(seconds=10)
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="ready",
            summary="cached summary",
            created_at=recent_timestamp,
            updated_at=recent_timestamp,
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    def unexpected_call(*args, **kwargs):
        raise AssertionError("force refresh cooldown should reuse the cached analysis")

    monkeypatch.setattr(
        repos_module.github_service, "get_repo_metadata", unexpected_call
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world", "force": True},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == repo_id
    assert response.json()["status"] == "ready"
    assert response.json()["summary"] == "cached summary"

    with database_module.SessionLocal() as db:
        repos = db.query(Repository).all()
        assert len(repos) == 1
        assert repos[0].status == "ready"


def test_rebuild_preserves_ai_fields_for_unchanged_files(client, monkeypatch):
    analyzed_at = datetime(2026, 1, 1)
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
        )
        db.add(repo)
        db.flush()
        repo_id = repo.id
        db.add(
            FileNode(
                repo_id=repo_id,
                file_path="src/app.py",
                language="python",
                line_count=2,
                import_count=0,
                ai_summary="saved summary",
                ai_summary_detail="saved detail",
                ai_complexity="low",
                ai_role="utility",
                analyzed_at=analyzed_at,
            )
        )
        db.commit()

    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_tree",
        lambda owner, repo_name, ref: (
            [{"path": "src/app.py"}] if ref == commit_sha else []
        ),
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "fetch_files_concurrent",
        lambda owner, repo_name, ref, file_paths: (
            {"src/app.py": "one\\ntwo\\n"} if ref == commit_sha else {}
        ),
    )
    monkeypatch.setattr(
        repos_module.github_service, "get_commit_sha", lambda *args: commit_sha
    )
    monkeypatch.setattr(
        repos_module.code_parser,
        "parse",
        lambda path, content: {
            "imports": [],
            "language": "python",
            "line_count": 2,
        },
    )
    monkeypatch.setattr(
        repos_module.ai_service,
        "generate_repo_summary",
        lambda *args, **kwargs: "fresh repository summary",
    )

    asyncio.run(
        repos_module._build_repo_analysis(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    with database_module.SessionLocal() as db:
        node = (
            db.query(FileNode)
            .filter(FileNode.repo_id == repo_id, FileNode.file_path == "src/app.py")
            .one()
        )
        assert node.ai_summary == "saved summary"
        assert node.ai_summary_detail == "saved detail"
        assert node.ai_complexity == "low"
        assert node.ai_role == "utility"
        assert node.analyzed_at == analyzed_at
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.commit_sha == commit_sha


def test_get_repo_requires_api_key_when_configured(client):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="ready",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    response = client.get(f"/repos/{repo_id}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_list_repos_requires_api_key_when_configured(client):
    response = client.get("/repos/")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_list_repos_paginates_filters_and_preserves_created_order(client):
    with database_module.SessionLocal() as db:
        db.add_all(
            [
                Repository(
                    owner="octocat",
                    repo_name=f"repo-{index}",
                    github_url=f"https://github.com/octocat/repo-{index}",
                    default_branch="main",
                    status="ready" if index % 2 == 0 else "failed",
                    created_at=datetime(2026, 1, 1) + timedelta(seconds=index),
                )
                for index in range(205)
            ]
        )
        db.commit()

    headers = {"X-API-Key": "test-api-key"}
    default_response = client.get("/repos/", headers=headers)
    page_response = client.get("/repos/?limit=3&offset=2", headers=headers)
    filtered_response = client.get(
        "/repos/?limit=2&offset=1&status=ready", headers=headers
    )
    max_page_response = client.get("/repos/?limit=200", headers=headers)
    invalid_limit_response = client.get("/repos/?limit=201", headers=headers)

    assert default_response.status_code == 200
    assert len(default_response.json()) == 50
    assert [repo["repo_name"] for repo in page_response.json()] == [
        "repo-202",
        "repo-201",
        "repo-200",
    ]
    assert [repo["repo_name"] for repo in filtered_response.json()] == [
        "repo-202",
        "repo-200",
    ]
    assert len(max_page_response.json()) == 200
    assert invalid_limit_response.status_code == 422


def test_analyze_rejects_missing_api_key(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    missing_key_response = client.post(
        "/repos/analyze", json={"github_url": "https://github.com/octocat/hello-world"}
    )

    assert missing_key_response.status_code == 401
    assert missing_key_response.json()["detail"] == "Invalid API key"


def test_analyze_rejects_invalid_api_key(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    invalid_key_response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "wrong-key"},
    )

    assert invalid_key_response.status_code == 401
    assert invalid_key_response.json()["detail"] == "Invalid API key"


def test_analyze_accepts_valid_api_key(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    valid_key_response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert valid_key_response.status_code == 200


def test_analyze_claims_repo_lock_before_background_work(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200

    with database_module.SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.github_url == "https://github.com/octocat/hello-world").first()
        assert repo is not None
        assert repo.locked_at is not None
        assert repo.worker_id is not None
        assert repo.status == "parsing"


def test_analyze_rejects_duplicate_in_progress_request_for_same_repo(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    first_response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Repository analysis is already in progress"


def test_concurrent_analyze_requests_one_succeeds(client, monkeypatch):
    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None)

    from concurrent.futures import ThreadPoolExecutor

    url = "https://github.com/octocat/hello-world"

    def do_post():
        return client.post(
            "/repos/analyze", json={"github_url": url}, headers={"X-API-Key": "test-api-key"}
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(do_post) for _ in range(2)]
        responses = [f.result() for f in futures]

    codes = sorted([r.status_code for r in responses])
    assert codes == [200, 409]

    with database_module.SessionLocal() as db:
        assert db.query(Repository).filter(Repository.github_url == url).count() == 1


def test_analyze_canonicalizes_repository_url_variants(client, monkeypatch):
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {
            "default_branch": "main",
            "full_name": "Owner/Repo",
        },
    )
    monkeypatch.setattr(
        repos_module, "_build_repo_analysis_with_timeout", lambda *args, **kwargs: None
    )

    urls = [
        "https://github.com/Owner/Repo",
        "https://github.com/Owner/Repo.git",
        "https://github.com/Owner/Repo/tree/main",
        "https://www.github.com/Owner/Repo",
        "https://github.com/Owner/Repo/",
        "https://github.com/Owner/Repo?tab=readme",
    ]
    responses = [
        client.post(
            "/repos/analyze",
            json={"github_url": url},
            headers={"X-API-Key": "test-api-key"},
        )
        for url in urls
    ]

    assert [response.status_code for response in responses] == [200, 409, 409, 409, 409, 409]
    with database_module.SessionLocal() as db:
        repos = db.query(Repository).all()
        assert len(repos) == 1
        assert repos[0].github_url == "https://github.com/owner/repo"
        assert repos[0].owner == "Owner"
        assert repos[0].repo_name == "Repo"


def test_analyze_rejects_when_rate_limited(client, monkeypatch):
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: False)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 429


def test_analyze_rejects_when_concurrency_cap_is_exhausted(client, monkeypatch):
    async def reject_acquire() -> bool:
        return False

    monkeypatch.setattr(
        repos_module.github_service, "parse_repo_url", lambda url: ("octocat", "hello-world")
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_repo_metadata",
        lambda owner, repo: {"default_branch": "main"},
    )
    monkeypatch.setattr(repos_module, "acquire_repo_analysis_slot", reject_acquire)
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Too many repository analyses are currently running"


def test_build_repo_analysis_with_timeout_sets_failed_when_slot_unavailable(client, monkeypatch):
    async def reject_acquire() -> bool:
        return False

    called = False

    async def fake_build_repo_analysis(*args, **kwargs):
        nonlocal called
        called = True

    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
            locked_at=datetime.now(timezone.utc),
            worker_id="worker-1",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    monkeypatch.setattr(repos_module, "acquire_repo_analysis_slot", reject_acquire)
    monkeypatch.setattr(repos_module, "_build_repo_analysis", fake_build_repo_analysis)

    import asyncio

    asyncio.run(
        repos_module._build_repo_analysis_with_timeout(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    assert called is False

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "failed"
        assert repo.error_message == "Analysis failed"
        assert repo.locked_at is None
        assert repo.worker_id is None


@pytest.mark.parametrize(
    ("failure", "expected_error"),
    [
        (GithubRateLimitError("GitHub rate limit reached"), "GitHub rate limit reached"),
        (
            RepoNotFoundError("https://github.com/octocat/missing"),
            "Repository not found: https://github.com/octocat/missing",
        ),
        (
            RepoPrivateError("https://github.com/octocat/private"),
            "Repository is private or access is denied: https://github.com/octocat/private",
        ),
        (RuntimeError("internal implementation detail"), "Analysis failed"),
    ],
)
def test_repo_analysis_stores_safe_failure_message(
    client, monkeypatch, failure, expected_error
):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    def fail_get_file_tree(*args):
        raise failure

    monkeypatch.setattr(repos_module.github_service, "get_file_tree", fail_get_file_tree)
    monkeypatch.setattr(
        repos_module.github_service,
        "get_commit_sha",
        lambda *args: "0123456789abcdef0123456789abcdef01234567",
    )

    asyncio.run(
        repos_module._build_repo_analysis(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "failed"
        assert repo.error_message == expected_error


def test_repo_analysis_timeout_stores_timeout_message(client, monkeypatch):
    async def acquire_slot():
        return True

    async def release_slot():
        return None

    async def slow_analysis(*args, **kwargs):
        await asyncio.sleep(1)

    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    monkeypatch.setattr(repos_module.settings, "ANALYSIS_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(repos_module, "acquire_repo_analysis_slot", acquire_slot)
    monkeypatch.setattr(repos_module, "release_repo_analysis_slot", release_slot)
    monkeypatch.setattr(repos_module, "_build_repo_analysis", slow_analysis)

    asyncio.run(
        repos_module._build_repo_analysis_with_timeout(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "failed"
        assert repo.error_message == "Analysis timed out"


def test_build_repo_analysis_marks_ready_when_ai_summary_fails(client, monkeypatch):
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
            locked_at=datetime.now(timezone.utc),
            worker_id="worker-1",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    observed_stages = []

    def get_stage():
        with database_module.SessionLocal() as db:
            repo = db.get(Repository, repo_id)
            assert repo is not None
            return repo.stage

    def get_file_tree(owner, repo_name, branch):
        assert branch == commit_sha
        observed_stages.append(get_stage())
        return [{"path": "src/app.py"}]

    def fetch_files(owner, repo_name, branch, file_paths):
        assert branch == commit_sha
        observed_stages.append(get_stage())
        return {"src/app.py": "print('hi')"}

    def parse_file(path, content):
        observed_stages.append(get_stage())
        return {"imports": [], "language": "python", "line_count": 1}

    def fail_summary(*args, **kwargs):
        observed_stages.append(get_stage())
        raise AIServiceError("AI summary generation failed")

    monkeypatch.setattr(repos_module.github_service, "get_file_tree", get_file_tree)
    monkeypatch.setattr(repos_module.github_service, "fetch_files_concurrent", fetch_files)
    monkeypatch.setattr(
        repos_module.github_service, "get_commit_sha", lambda *args: commit_sha
    )
    monkeypatch.setattr(repos_module.code_parser, "parse", parse_file)
    monkeypatch.setattr(
        repos_module.ai_service,
        "generate_repo_summary",
        fail_summary,
    )

    import asyncio

    asyncio.run(
        repos_module._build_repo_analysis(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
            client_ip="127.0.0.1",
        )
    )

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "ready"
        assert repo.commit_sha == commit_sha
        assert repo.stage is None
        assert repo.summary is None
        assert repo.locked_at is None
        assert repo.worker_id is None
    assert observed_stages == ["fetching", "fetching", "parsing", "summarizing"]


def test_fetch_manifest_excerpt_skips_missing_manifests(client, monkeypatch):
    missing_response = requests.Response()
    missing_response.status_code = 404
    missing_error = requests.HTTPError("missing", response=missing_response)
    calls = []

    def get_file_content(owner, repo_name, ref, path):
        calls.append(path)
        if path == "package.json":
            raise missing_error
        if path == "pyproject.toml":
            return "\n".join(f"line {index}" for index in range(45))
        raise AssertionError(f"Unexpected manifest fetch: {path}")

    monkeypatch.setattr(repos_module.github_service, "get_file_content", get_file_content)

    excerpt = repos_module._fetch_manifest_excerpt("octocat", "hello-world", "main")

    assert calls == ["package.json", "pyproject.toml"]
    assert excerpt is not None
    assert len(excerpt.splitlines()) == 40
    assert excerpt.splitlines()[0] == "line 0"
    assert excerpt.splitlines()[-1] == "line 39"


def test_build_repo_summary_uses_readme_manifest_and_top_files(client, monkeypatch):
    commit_sha = "0123456789abcdef0123456789abcdef01234567"
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            status="parsing",
        )
        db.add(repo)
        db.commit()
        repo_id = repo.id

    contents = {
        "README.md": "# Hello World\n" + ("readme " * 300),
        "src/a.py": "import src.b",
        "src/b.py": "import src.c",
        "src/c.py": "print('done')",
    }
    captured_summary = {}

    def missing_manifest(*args):
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("missing", response=response)

    monkeypatch.setattr(
        repos_module.github_service,
        "get_commit_sha",
        lambda *args: commit_sha,
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_tree",
        lambda *args: [{"path": path} for path in contents],
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "fetch_files_concurrent",
        lambda *args: contents,
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_content",
        missing_manifest,
    )
    monkeypatch.setattr(repos_module.code_parser, "parse", lambda path, content: {
        "imports": ["src.b"] if path.endswith("a.py") else ["src.c"] if path.endswith("b.py") else [],
        "language": "python",
        "line_count": 1,
    })
    monkeypatch.setattr(repos_module.settings, "AUTO_ANALYZE_TOP_FILES", 0)

    def generate_repo_summary(*args, **kwargs):
        captured_summary.update(kwargs)
        return "summary"

    monkeypatch.setattr(
        repos_module.ai_service,
        "generate_repo_summary",
        generate_repo_summary,
    )

    asyncio.run(
        repos_module._build_repo_analysis(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    assert captured_summary["readme_excerpt"] == contents["README.md"][:1500]
    assert captured_summary["manifest_excerpt"] is None
    assert captured_summary["top_files"][:2] == ["src/b.py", "src/c.py"]


def test_build_repo_analysis_uses_tsconfig_aliases_for_edges(client, monkeypatch):
    repo_id = _create_auto_analysis_repo()
    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        repo.status = "parsing"
        repo.repo_name = "hello-world"
        repo.github_url = "https://github.com/octocat/hello-world"
        db.commit()

    contents = {
        "src/App.jsx": "import api from '@/utils/api';",
        "src/utils/api.ts": "export default {};",
    }
    monkeypatch.setattr(repos_module.settings, "AUTO_ANALYZE_TOP_FILES", 0)
    monkeypatch.setattr(repos_module.github_service, "get_commit_sha", lambda *args: "a" * 40)
    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_tree",
        lambda *args: [{"path": path} for path in contents],
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "fetch_files_concurrent",
        lambda *args: contents,
    )
    monkeypatch.setattr(
        repos_module.github_service,
        "get_typescript_config",
        lambda *args: '{"compilerOptions":{"paths":{"@/*":["src/*"]}}}',
    )
    monkeypatch.setattr(
        repos_module.code_parser,
        "parse",
        lambda path, _content: {
            "imports": ["@/utils/api"] if path == "src/App.jsx" else [],
            "language": "javascript",
            "line_count": 1,
        },
    )
    monkeypatch.setattr(
        repos_module.ai_service,
        "generate_repo_summary",
        lambda *args, **kwargs: "summary",
    )

    asyncio.run(
        repos_module._build_repo_analysis(
            repo_id,
            "octocat",
            "hello-world",
            "https://github.com/octocat/hello-world",
            "main",
        )
    )

    with database_module.SessionLocal() as db:
        edges = db.query(FileEdge).filter(FileEdge.repo_id == repo_id).all()
    assert [(edge.source, edge.target) for edge in edges] == [
        ("src/App.jsx", "src/utils/api.ts")
    ]


def _create_auto_analysis_repo():
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="auto-analysis",
            github_url="https://github.com/octocat/auto-analysis",
            default_branch="main",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            status="ready",
        )
        db.add(repo)
        db.flush()
        repo_id = repo.id
        for path in ["src/a.py", "src/b.py", "src/c.py"]:
            db.add(
                FileNode(
                    repo_id=repo_id,
                    file_path=path,
                    language="python",
                    line_count=1,
                    import_count=0,
                )
            )
        db.add_all(
            [
                FileEdge(repo_id=repo_id, source="src/b.py", target="src/a.py"),
                FileEdge(repo_id=repo_id, source="src/c.py", target="src/a.py"),
            ]
        )
        db.commit()
        return repo_id


def test_auto_file_analysis_stops_when_ai_budget_is_exceeded(client, monkeypatch):
    repo_id = _create_auto_analysis_repo()
    monkeypatch.setattr(repos_module.settings, "AUTO_ANALYZE_TOP_FILES", 3)
    fetched_paths = []
    analyzed_paths = []

    def get_file_content(owner, repo_name, ref, file_path):
        fetched_paths.append((owner, repo_name, ref, file_path))
        return "print('hi')"

    async def analyze_file(file_path, content, client_ip=None):
        analyzed_paths.append((file_path, client_ip))
        raise AIBudgetExceededError("budget exceeded")

    monkeypatch.setattr(repos_module.github_service, "get_file_content", get_file_content)
    monkeypatch.setattr(repos_module.ai_service, "analyze_file", analyze_file)

    asyncio.run(repos_module._auto_analyze_top_files(repo_id))

    assert analyzed_paths == [("src/a.py", "system:auto")]
    assert fetched_paths == [
        ("octocat", "auto-analysis", "0123456789abcdef0123456789abcdef01234567", "src/a.py")
    ]
    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "ready"
        assert repo.stage is None


def test_auto_file_analysis_is_disabled_at_zero(client, monkeypatch):
    repo_id = _create_auto_analysis_repo()
    monkeypatch.setattr(repos_module.settings, "AUTO_ANALYZE_TOP_FILES", 0)
    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_content",
        lambda *args: pytest.fail("GitHub content should not be fetched when auto-analysis is disabled"),
    )

    asyncio.run(repos_module._auto_analyze_top_files(repo_id))

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        assert repo.status == "ready"


def test_auto_file_analysis_persists_results_without_changing_repo_status(client, monkeypatch):
    repo_id = _create_auto_analysis_repo()
    monkeypatch.setattr(repos_module.settings, "AUTO_ANALYZE_TOP_FILES", 1)
    monkeypatch.setattr(
        repos_module.github_service,
        "get_file_content",
        lambda *args: "print('hi')",
    )
    analyzed_clients = []

    async def analyze_file(file_path, content, client_ip=None):
        analyzed_clients.append(client_ip)
        return {
            "summary": "summary",
            "summary_detail": "detail",
            "complexity": "low",
            "role": "utility",
        }

    monkeypatch.setattr(repos_module.ai_service, "analyze_file", analyze_file)

    asyncio.run(repos_module._auto_analyze_top_files(repo_id))

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        node = (
            db.query(FileNode)
            .filter(FileNode.repo_id == repo_id, FileNode.file_path == "src/a.py")
            .one()
        )
        assert repo is not None
        assert repo.status == "ready"
        assert repo.stage is None
        assert node.ai_complexity == "low"
        assert node.ai_role == "utility"
        assert node.analyzed_at is not None
    assert analyzed_clients == ["system:auto"]


@pytest.mark.parametrize(
    ("commit_sha", "expected_ref"),
    [
        ("0123456789abcdef0123456789abcdef01234567", "0123456789abcdef0123456789abcdef01234567"),
        (None, "main"),
    ],
)
def test_file_analysis_fetches_from_pinned_commit_or_legacy_branch(
    client, monkeypatch, commit_sha, expected_ref
):
    with database_module.SessionLocal() as db:
        repo = Repository(
            owner="octocat",
            repo_name="hello-world",
            github_url="https://github.com/octocat/hello-world",
            default_branch="main",
            commit_sha=commit_sha,
            status="ready",
        )
        db.add(repo)
        db.flush()
        repo_id = repo.id
        db.add(
            FileNode(
                repo_id=repo_id,
                file_path="src/app.py",
                language="python",
                line_count=1,
                import_count=0,
            )
        )
        db.commit()

    fetched_refs = []

    def get_file_content(owner, repo_name, ref, file_path):
        fetched_refs.append(ref)
        return "print('hi')"

    async def analyze_file(file_path, content, client_ip=None):
        return {
            "summary": "summary",
            "summary_detail": "detail",
            "complexity": "low",
            "role": "utility",
        }

    monkeypatch.setattr(files_module.file_rate_limiter, "allow", lambda ip: True)
    monkeypatch.setattr(files_module.github_service, "get_file_content", get_file_content)
    monkeypatch.setattr(files_module.ai_service, "analyze_file", analyze_file)

    response = client.post(
        "/files/analyze",
        json={"repo_id": repo_id, "file_path": "src/app.py"},
        headers={"X-API-Key": "test-api-key"},
    )

    assert response.status_code == 200
    assert fetched_refs == [expected_ref]


def test_resolve_client_ip_ignores_spoofed_forwarded_header_by_default(monkeypatch):
    monkeypatch.setattr(rate_limit_module.settings, "TRUST_PROXY_HEADERS", False)

    class FakeClient:
        host = "127.0.0.1"

    class FakeRequest:
        def __init__(self):
            self.headers = {"x-forwarded-for": "8.8.8.8, 9.9.9.9"}
            self.client = FakeClient()

    assert rate_limit_module.IPRateLimiter.resolve_client_ip(FakeRequest()) == "127.0.0.1"


def test_resume_pending_repo_analyses_schedules_background_tasks(tmp_path, monkeypatch):
    db_path = tmp_path / "pending.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)

    Base.metadata.create_all(bind=engine)

    with test_session_local() as db:
        db.add(
            Repository(
                github_url="https://github.com/octocat/hello-world",
                repo_name="hello-world",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
            )
        )
        db.commit()

    scheduled: list[tuple] = []

    class FakeTaskLoop:
        def create_task(self, coro):
            coro.close()
            scheduled.append(coro)

    monkeypatch.setattr(repos_module.asyncio, "get_running_loop", lambda: FakeTaskLoop())

    import asyncio

    # Ensure the startup mutex allows reclaim to proceed
    monkeypatch.setattr(repos_module, "RedisMutex", FakeStartupMutex)

    asyncio.run(repos_module.resume_pending_repo_analyses())

    assert len(scheduled) == 1


def test_deleting_repository_cascades_to_related_rows(client):
    with database_module.SessionLocal() as db:
        repo = Repository(
            github_url="https://github.com/octocat/cascade-demo",
            repo_name="cascade-demo",
            owner="octocat",
            default_branch="main",
            total_files=1,
            status="ready",
        )
        db.add(repo)
        db.flush()

        db.add(
            FileNode(
                repo_id=repo.id,
                file_path="src/app.py",
                language="python",
                line_count=1,
                import_count=0,
            )
        )
        db.add(FileEdge(repo_id=repo.id, source="src/app.py", target="src/utils.py"))
        db.commit()
        repo_id = repo.id

    with database_module.SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        db.delete(repo)
        db.commit()

    with database_module.SessionLocal() as db:
        assert db.query(Repository).filter(Repository.id == repo_id).count() == 0
        assert db.query(FileNode).filter(FileNode.repo_id == repo_id).count() == 0
        assert db.query(FileEdge).filter(FileEdge.repo_id == repo_id).count() == 0


def test_resume_pending_repo_analyses_claims_and_skips(tmp_path, monkeypatch):
    db_path = tmp_path / "pending2.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)

    Base.metadata.create_all(bind=engine)

    with test_session_local() as db:
        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1000)
        fresh_time = datetime.now(timezone.utc).replace(tzinfo=None)

        # stale locked repo should be reclaimed
        db.add(
            Repository(
                github_url="https://github.com/octocat/stale",
                repo_name="stale",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
                locked_at=stale_time,
                worker_id="old",
            )
        )

        # fresh locked repo should be skipped
        db.add(
            Repository(
                github_url="https://github.com/octocat/fresh",
                repo_name="fresh",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
                locked_at=fresh_time,
                worker_id="other",
            )
        )

        db.commit()

    scheduled: list[tuple] = []

    class FakeTaskLoop:
        def create_task(self, coro):
            coro.close()
            scheduled.append(coro)

    monkeypatch.setattr(repos_module.asyncio, "get_running_loop", lambda: FakeTaskLoop())

    # ensure reclaim threshold small for test
    monkeypatch.setattr(
        repos_module, "settings", repos_module.settings.__class__(RECLAIM_LOCK_AFTER_SECONDS=60)
    )

    import asyncio

    # Ensure the startup mutex allows reclaim to proceed
    monkeypatch.setattr(repos_module, "RedisMutex", FakeStartupMutex)

    asyncio.run(repos_module.resume_pending_repo_analyses())

    # only the stale record should have been scheduled
    assert len(scheduled) == 1


def test_startup_reclaim_lock_skips_second_call(tmp_path, monkeypatch):
    db_path = tmp_path / "pending_lock.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)

    Base.metadata.create_all(bind=engine)

    with test_session_local() as db:
        db.add(
            Repository(
                github_url="https://github.com/octocat/lock",
                repo_name="lock",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
            )
        )
        db.commit()

    scheduled: list[tuple] = []

    class FakeLoop:
        def create_task(self, coro):
            coro.close()
            scheduled.append(coro)

    monkeypatch.setattr(repos_module.asyncio, "get_running_loop", lambda: FakeLoop())

    # Make RedisMutex.acquire return a token on first call, None on second.
    side = ["token", None]

    async def fake_acquire(self, name, timeout=20.0, poll_interval=0.2):
        return side.pop(0)

    async def fake_release(self, name, token):
        return None

    monkeypatch.setattr(repos_module.RedisMutex, "acquire", fake_acquire)
    monkeypatch.setattr(repos_module.RedisMutex, "release", fake_release)

    import asyncio

    asyncio.run(repos_module.resume_pending_repo_analyses())
    asyncio.run(repos_module.resume_pending_repo_analyses())

    assert len(scheduled) == 1


def test_resume_pending_repo_analyses_logs_when_no_running_loop(tmp_path, monkeypatch):
    db_path = tmp_path / "pending_noloop.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)

    Base.metadata.create_all(bind=engine)

    with test_session_local() as db:
        db.add(
            Repository(
                github_url="https://github.com/octocat/noloop",
                repo_name="noloop",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
            )
        )
        db.commit()

    # Simulate no running loop when scheduling
    def raise_runtime():
        raise RuntimeError()

    monkeypatch.setattr(repos_module.asyncio, "get_running_loop", lambda: (_ for _ in ()).throw(RuntimeError()))

    async def fake_acquire(self, name, timeout=20.0, poll_interval=0.2):
        return "token"

    async def fake_release(self, name, token):
        return None

    monkeypatch.setattr(repos_module.RedisMutex, "acquire", fake_acquire)
    monkeypatch.setattr(repos_module.RedisMutex, "release", fake_release)

    import asyncio

    # Should not raise despite no running loop
    asyncio.run(repos_module.resume_pending_repo_analyses())


def test_resume_pending_repo_analyses_reclaims_crashed_worker_lock_after_timeout(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "pending-crash.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    test_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(repos_module, "SessionLocal", test_session_local)
    monkeypatch.setattr(
        repos_module,
        "settings",
        repos_module.settings.__class__(RECLAIM_LOCK_AFTER_SECONDS=1),
    )

    Base.metadata.create_all(bind=engine)

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=5)

    with test_session_local() as db:
        db.add(
            Repository(
                github_url="https://github.com/octocat/crashed",
                repo_name="crashed",
                owner="octocat",
                default_branch="main",
                total_files=0,
                status="parsing",
                locked_at=stale_time,
                worker_id="crashed-worker",
            )
        )
        db.commit()

    scheduled: list[tuple] = []

    class FakeTaskLoop:
        def create_task(self, coro):
            coro.close()
            scheduled.append(coro)

    monkeypatch.setattr(repos_module.asyncio, "get_running_loop", lambda: FakeTaskLoop())

    import asyncio

    # Ensure the startup mutex allows reclaim to proceed
    monkeypatch.setattr(repos_module, "RedisMutex", FakeStartupMutex)

    asyncio.run(repos_module.resume_pending_repo_analyses())

    assert len(scheduled) == 1

    with test_session_local() as db:
        repo = db.query(Repository).filter(Repository.github_url == "https://github.com/octocat/crashed").first()
        assert repo is not None
        assert repo.locked_at is not None
        assert repo.worker_id != "crashed-worker"