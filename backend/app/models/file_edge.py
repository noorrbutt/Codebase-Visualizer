from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class FileEdge(Base):
    __tablename__ = "file_edge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repository.id"), nullable=False)
    source = Column(String, nullable=False)
    target = Column(String, nullable=False)

    repository = relationship("Repository", backref="edges")

    def __repr__(self) -> str:
        return f"<FileEdge(id={self.id}, repo_id={self.repo_id}, source={self.source}, target={self.target})>"
