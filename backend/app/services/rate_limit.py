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
        now = int(time.time())
        redis_client = self._get_redis_client()
        key = f"rate_limit:{ip_address}"

        cutoff = now - self.window_seconds
        redis_client.zremrangebyscore(key, float("-inf"), cutoff)
        request_count = int(redis_client.zcard(key))

        if request_count >= self.max_requests:
            return False

        member = f"{now}:{time.time_ns()}"
        redis_client.zadd(key, {member: float(now)})
        redis_client.expire(key, self.window_seconds + 1)
        return True
