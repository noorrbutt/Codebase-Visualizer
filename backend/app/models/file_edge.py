from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship

from app.database import Base


class FileEdge(Base):
    __tablename__ = "file_edge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repository.id"), nullable=False, index=True)
    source = Column(String, nullable=False)
    target = Column(String, nullable=False)

    repository = relationship("Repository", backref=backref("edges", cascade="all, delete-orphan"))
