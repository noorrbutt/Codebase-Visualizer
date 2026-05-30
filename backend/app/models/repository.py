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
    total_files = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="parsing")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Repository(id={self.id}, owner={self.owner}, repo_name={self.repo_name}, "
            f"status={self.status}, total_files={self.total_files})>"
        )
