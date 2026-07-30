from __future__ import annotations

from fastapi import Header


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    return None
