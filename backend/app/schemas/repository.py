from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class AnalyzeRequest(BaseModel):
    github_url: HttpUrl
    force: bool = False



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
    ai_summary_detail: str | None
    ai_complexity: str | None
    ai_role: str | None
    complexity: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class MetricNode(BaseModel):
    path: str
    count: int


class GraphMetrics(BaseModel):
    cycle_count: int
    cycles: list[list[str]]
    top_fan_in: list[MetricNode]
    top_fan_out: list[MetricNode]
    orphan_count: int
    orphans: list[str]


class AnalyzeResponse(BaseModel):
    id: int
    repo_name: str
    owner: str
    default_branch: str
    status: str
    summary: str | None
    total_files: int
    nodes: list[FileNodeOut]
    edges: list[FileEdge]
    metrics: GraphMetrics | None = None
    discovered_files: int | None = None
    truncated: bool = False

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
