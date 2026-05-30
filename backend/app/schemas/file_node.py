from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileAnalyzeRequest(BaseModel):
    repo_id: int
    file_path: str
    model_config = ConfigDict()


class FileAnalyzeResponse(BaseModel):
    file_path: str
    ai_summary: str
    ai_complexity: str
    ai_role: str
    model_config = ConfigDict(from_attributes=True)
