from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Repository(Base):
    __tablename__ = "repository"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_url = Column(String, unique=True, nullable=False)
    repo_name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    default_branch = Column(String, nullable=False, server_default="main")
    commit_sha = Column(String, nullable=True)
    total_files = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="parsing")
    stage = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)
    # Locking fields used to claim long-running analysis work across restarts/workers
    locked_at = Column(DateTime, nullable=True)
    worker_id = Column(String, nullable=True)
