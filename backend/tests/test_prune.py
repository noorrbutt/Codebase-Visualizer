from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file_edge import FileEdge
from app.models.file_node import FileNode
from app.models.repository import Repository
from scripts.prune_repos import prune_repositories


def _session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'prune.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _add_repo(session, name, status, updated_at, with_graph=False):
    repo = Repository(
        github_url=f"https://github.com/octocat/{name}",
        repo_name=name,
        owner="octocat",
        default_branch="main",
        total_files=2 if with_graph else 0,
        status=status,
        updated_at=updated_at,
    )
    session.add(repo)
    session.flush()
    if with_graph:
        session.add_all(
            [
                FileNode(
                    repo_id=repo.id,
                    file_path="src/a.py",
                    language="python",
                    line_count=1,
                    import_count=0,
                ),
                FileNode(
                    repo_id=repo.id,
                    file_path="src/b.py",
                    language="python",
                    line_count=1,
                    import_count=0,
                ),
                FileEdge(repo_id=repo.id, source="src/a.py", target="src/b.py"),
            ]
        )
    return repo.id


def test_prune_dry_run_counts_only_old_finished_repositories(tmp_path):
    engine, session_factory = _session_factory(tmp_path)
    now = datetime(2026, 11, 28, 12, 0)
    old = now - timedelta(days=31)
    recent = now - timedelta(days=10)

    try:
        with session_factory() as session:
            _add_repo(session, "old-ready", "ready", old, with_graph=True)
            _add_repo(session, "old-failed", "failed", old)
            _add_repo(session, "old-parsing", "parsing", old)
            _add_repo(session, "recent-ready", "ready", recent)
            _add_repo(session, "unknown-age", "failed", None)
            session.commit()

        counts = prune_repositories(
            days=30, dry_run=True, session_factory=session_factory, now=now
        )

        assert counts == {"repositories": 2, "nodes": 2, "edges": 1}
        with session_factory() as session:
            assert session.query(Repository).count() == 5
            assert session.query(FileNode).count() == 2
            assert session.query(FileEdge).count() == 1
            assert (
                session.query(Repository)
                .filter(Repository.repo_name == "old-parsing")
                .one()
                .status
                == "parsing"
            )
    finally:
        engine.dispose()


def test_prune_deletes_old_ready_and_failed_graph_rows(tmp_path):
    engine, session_factory = _session_factory(tmp_path)
    now = datetime(2026, 11, 28, 12, 0)
    old = now - timedelta(days=31)

    try:
        with session_factory() as session:
            _add_repo(session, "old-ready", "ready", old, with_graph=True)
            _add_repo(session, "old-failed", "failed", old, with_graph=True)
            _add_repo(session, "old-parsing", "parsing", old, with_graph=True)
            session.commit()

        counts = prune_repositories(
            days=30, session_factory=session_factory, now=now
        )

        assert counts == {"repositories": 2, "nodes": 4, "edges": 2}
        with session_factory() as session:
            remaining = session.query(Repository).all()
            assert [(repo.repo_name, repo.status) for repo in remaining] == [
                ("old-parsing", "parsing")
            ]
            assert session.query(FileNode).count() == 2
            assert session.query(FileEdge).count() == 1
    finally:
        engine.dispose()
