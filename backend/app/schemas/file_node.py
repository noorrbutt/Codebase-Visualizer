from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileAnalyzeRequest(BaseModel):
    repo_id: int
    file_path: str



class FileAnalyzeResponse(BaseModel):
    file_path: str
    ai_summary: str | None
    ai_complexity: str | None
    ai_role: str | None
    model_config = ConfigDict(from_attributes=True)
