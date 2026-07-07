from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from app.config import settings


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")

    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")
