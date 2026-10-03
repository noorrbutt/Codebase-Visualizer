from __future__ import annotations

import ipaddress
import time

from fastapi import Request
from redis import Redis

from app.config import settings
from app.logging import get_logger
from app.services.redis_client import get_redis_client

logger = get_logger(__name__)


class IPRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, redis_client: Redis | None = None) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis_client = redis_client

    @staticmethod
    def resolve_client_ip(request: Request) -> str:
        client_host = request.client.host if request.client and request.client.host else None

        if settings.TRUST_PROXY_HEADERS and settings.TRUSTED_PROXY_COUNT > 0:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            logger.debug("client.host={} x-forwarded-for={!r}", client_host, forwarded_for)

            # Each trusted proxy appends the address it saw, so the entry that many
            # positions from the right is the one the outermost trusted proxy recorded.
            entries = [entry.strip() for entry in forwarded_for.split(",")]
            if len(entries) >= settings.TRUSTED_PROXY_COUNT:
                candidate = entries[-settings.TRUSTED_PROXY_COUNT]
                try:
                    return str(ipaddress.ip_address(candidate))
                except ValueError:
                    pass
        elif settings.TRUST_PROXY_HEADERS:
            # Count of 0 keeps the legacy behavior: trust the leftmost entry.
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                forwarded_ip = forwarded_for.split(",")[0].strip()
                if forwarded_ip:
                    return forwarded_ip

        if client_host:
            return client_host

        return "unknown"

    def _get_redis_client(self) -> Redis:
        return self._redis_client or get_redis_client()

    def allow(self, ip_address: str) -> bool:
        """Fixed-window counter: O(1) redis ops per call.

        Requests are bucketed into non-overlapping windows of size
        `window_seconds`. Each bucket has its own counter key that expires
        on its own, so there is no need to scan or sum multiple keys.
        """
        now = time.time()
        window_id = int(now // self.window_seconds)
        redis_client = self._get_redis_client()
        key = f"rate_limit:{ip_address}:{window_id}"

        count = int(redis_client.incr(key))
        if count == 1:
            redis_client.expire(key, self.window_seconds + 1)

        return count <= self.max_requests