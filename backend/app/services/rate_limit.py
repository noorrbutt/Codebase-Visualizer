from __future__ import annotations

import time

from fastapi import Request
from redis import Redis

from app.services.redis_client import get_redis_client


class IPRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, redis_client: Redis | None = None) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis_client = redis_client

    @staticmethod
    def resolve_client_ip(request: Request) -> str:
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
        key_prefix = f"rate_limit:{ip_address}:"

        current_key = f"{key_prefix}{now}"
        request_count = int(redis_client.incr(current_key))
        if request_count == 1:
            redis_client.expire(current_key, self.window_seconds + 1)

        window_total = 0
        for offset in range(self.window_seconds):
            bucket_key = f"{key_prefix}{now - offset}"
            value = redis_client.get(bucket_key)
            if value is not None:
                window_total += int(value)

        return window_total <= self.max_requests
