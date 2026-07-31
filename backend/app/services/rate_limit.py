from __future__ import annotations

import time

from fastapi import Request
from redis import Redis

from app.config import settings
from app.services.redis_client import get_redis_client


class IPRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, redis_client: Redis | None = None) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis_client = redis_client

    @staticmethod
    def resolve_client_ip(request: Request) -> str:
        if settings.TRUST_PROXY_HEADERS:
            # Enabling this later requires a trusted proxy configuration (for example
            # trusted proxy count/IPs), not just flipping the flag.
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                forwarded_ip = forwarded_for.split(",")[0].strip()
                if forwarded_ip:
                    return forwarded_ip

        if request.client and request.client.host:
            return request.client.host

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