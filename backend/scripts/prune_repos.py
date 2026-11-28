from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models.file_edge import FileEdge  # noqa: E402
from app.models.file_node import FileNode  # noqa: E402
from app.models.repository import Repository  # noqa: E402


SessionFactory = Callable[[], Session]


def prune_repositories(
    days: int = 30,
    dry_run: bool = False,
    session_factory: SessionFactory = SessionLocal,
    now: datetime | None = None,
) -> dict[str, int]:
    if days < 1:
        raise ValueError("days must be at least 1")

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is not None:
        reference_time = reference_time.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = reference_time - timedelta(days=days)

    with session_factory() as session:
        with session.begin():
            repo_ids = [
                repo_id
                for (repo_id,) in session.query(Repository.id)
                .filter(
                    Repository.status.in_(("failed", "ready")),
                    Repository.updated_at.is_not(None),
                    Repository.updated_at < cutoff,
                )
                .all()
            ]

            if not repo_ids:
                return {"repositories": 0, "nodes": 0, "edges": 0}

            node_query = session.query(FileNode).filter(FileNode.repo_id.in_(repo_ids))
            edge_query = session.query(FileEdge).filter(FileEdge.repo_id.in_(repo_ids))
            counts = {
                "repositories": len(repo_ids),
                "nodes": node_query.count(),
                "edges": edge_query.count(),
            }

            if not dry_run:
                node_query.delete(synchronize_session=False)
                edge_query.delete(synchronize_session=False)
                session.query(Repository).filter(
                    Repository.id.in_(repo_ids)
                ).delete(synchronize_session=False)

            return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Delete old ready and failed repository analyses."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Delete eligible repositories older than this many days (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report repository, file-node, and edge counts without deleting.",
    )
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be at least 1")

    counts = prune_repositories(days=args.days, dry_run=args.dry_run)
    mode = "Would delete" if args.dry_run else "Deleted"
    print(
        f"{mode}: {counts['repositories']} repositories, "
        f"{counts['nodes']} file nodes, {counts['edges']} edges"
    )


if __name__ == "__main__":
    main()
