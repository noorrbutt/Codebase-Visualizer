from __future__ import annotations

from fastapi import Header, HTTPException
import secrets

from app.config import settings


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if settings.API_KEY is None:
        return None

    if not secrets.compare_digest(x_api_key or "", settings.API_KEY or ""):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return None