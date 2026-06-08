from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class AnalyzeRequest(BaseModel):
    github_url: HttpUrl
    model_config = ConfigDict()


class FileEdge(BaseModel):
    source: str
    target: str
    model_config = ConfigDict(from_attributes=True)


class FileNodeOut(BaseModel):
    id: int
    path: str
    language: str | None
    line_count: int
    import_count: int
    ai_summary: str | None
    ai_complexity: str | None
    ai_role: str | None

    model_config = ConfigDict(from_attributes=True)


class AnalyzeResponse(BaseModel):
    id: int
    repo_name: str
    owner: str
    default_branch: str
    status: str
    summary: str | None
    nodes: list[FileNodeOut]
    edges: list[FileEdge]

    model_config = ConfigDict(from_attributes=True)


class RepoListItem(BaseModel):
    id: int
    repo_name: str
    owner: str
    github_url: str
    status: str
    total_files: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
