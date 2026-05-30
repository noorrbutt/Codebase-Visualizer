from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class FileNode(Base):
    __tablename__ = "file_node"
    __table_args__ = (UniqueConstraint("repo_id", "file_path", name="uq_repo_file_path"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repository.id"), nullable=False)
    file_path = Column(String, nullable=False)
    language = Column(String, nullable=True)
    line_count = Column(Integer, nullable=False, default=0)
    import_count = Column(Integer, nullable=False, default=0)
    ai_summary = Column(Text, nullable=True)
    ai_complexity = Column(String, nullable=True)
    ai_role = Column(String, nullable=True)
    analyzed_at = Column(DateTime, nullable=True)

    repository = relationship("Repository", backref="file_nodes")

    def __repr__(self) -> str:
        return (
            f"<FileNode(id={self.id}, repo_id={self.repo_id}, file_path={self.file_path}, "
            f"language={self.language}, import_count={self.import_count})>"
        )
