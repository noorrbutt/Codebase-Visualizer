from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.routes.repos as repos_module
import app.database as database_module
import app.main as main_module
import app.services.rate_limit as rate_limit_module
from app.database import Base
from app.models.file_edge import FileEdge
from app.models.file_node import FileNode
from app.models.repository import Repository
from app.main import app


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

    status_response = client.get(f"/repos/{repo_id}/status")
    detail_response = client.get(f"/repos/{repo_id}")

    assert status_response.status_code == 200
    assert status_response.json() == {"status": "ready"}
    assert detail_response.status_code == 200
    assert detail_response.json()["nodes"][0]["path"] == "src/app.py"
    assert detail_response.json()["edges"][0]["source"] == "src/app.py"


def test_analyze_does_not_require_api_key(client, monkeypatch):
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

    assert missing_key_response.status_code == 200


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
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Repository analysis is already in progress"


def test_analyze_rejects_when_rate_limited(client, monkeypatch):
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: False)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
    )

    assert response.status_code == 429


def test_analyze_rejects_when_concurrency_cap_is_exhausted(client, monkeypatch):
    async def reject_acquire() -> bool:
        return False

    monkeypatch.setattr(repos_module, "acquire_repo_analysis_slot", reject_acquire)
    monkeypatch.setattr(repos_module.repo_rate_limiter, "allow", lambda ip: True)

    response = client.post(
        "/repos/analyze",
        json={"github_url": "https://github.com/octocat/hello-world"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Too many repository analyses are currently running"


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

    repos_module.resume_pending_repo_analyses()

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
        stale_time = datetime.utcnow() - timedelta(seconds=1000)
        fresh_time = datetime.utcnow()

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

    repos_module.resume_pending_repo_analyses()

    # only the stale record should have been scheduled
    assert len(scheduled) == 1


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

    repos_module.resume_pending_repo_analyses()

    assert len(scheduled) == 1

    with test_session_local() as db:
        repo = db.query(Repository).filter(Repository.github_url == "https://github.com/octocat/crashed").first()
        assert repo is not None
        assert repo.locked_at is not None
        assert repo.worker_id != "crashed-worker"
