from __future__ import annotations

import asyncio
import time
import uuid

from redis import Redis

from app.services.redis_client import get_redis_client


class RedisConcurrencyGate:
    """Distributed cap on concurrently running repo analyses.

    Backed by a Redis sorted set used as an expiring semaphore: each
    acquired slot is a member scored by its acquisition time. If a worker
    crashes or a Render instance sleeps mid-analysis without releasing its
    slot, that slot ages out after `slot_ttl_seconds` instead of leaking
    the counter forever (which a plain Redis INCR/DECR counter would do).

    The acquire check (ZREMRANGEBYSCORE + ZCARD + ZADD) is three round
    trips rather than one atomic Lua script, so two callers arriving in
    the same instant could both slip through when exactly one slot is
    left, admitting max+1 briefly. Given this app's traffic (a single
    free-tier instance, low concurrent usage), that's an acceptable
    trade-off for keeping the Redis surface to plain commands that are
    easy to fake in tests without a real server or Lua support.
    """

    KEY = "repo_analysis:semaphore"

    def __init__(
        self,
        max_concurrent_analyses: int,
        slot_ttl_seconds: int = 180,
        redis_client: Redis | None = None,
    ) -> None:
        self._max_concurrent_analyses = max_concurrent_analyses
        self._slot_ttl_seconds = slot_ttl_seconds
        self._redis_client = redis_client
        self._held_token: str | None = None

    def _client(self) -> Redis:
        return self._redis_client or get_redis_client()

    def _try_acquire_sync(self) -> str | None:
        client = self._client()
        now = time.time()
        token = uuid.uuid4().hex

        client.zremrangebyscore(self.KEY, "-inf", now - self._slot_ttl_seconds)
        if client.zcard(self.KEY) < self._max_concurrent_analyses:
            client.zadd(self.KEY, {token: now})
            return token
        return None

    def _release_sync(self, token: str) -> None:
        client = self._client()
        client.zrem(self.KEY, token)

    async def try_acquire(self) -> bool:
        token = await asyncio.to_thread(self._try_acquire_sync)
        if token is None:
            return False
        # One gate instance is only ever used for one in-flight acquire at a
        # time in this codebase (see acquire/release_repo_analysis_slot
        # below), so tracking a single held token here is sufficient.
        self._held_token = token
        return True

    async def release(self) -> None:
        if self._held_token is None:
            return
        token, self._held_token = self._held_token, None
        await asyncio.to_thread(self._release_sync, token)


class RedisMutex:
    """Distributed per-key mutex backed by Redis SET NX EX.

    Replaces a module-level `dict[str, asyncio.Lock]`, which only
    coordinated requests within a single process and was wiped on every
    restart. Acquisition polls with a timeout rather than blocking forever,
    since a distributed lock can otherwise wait indefinitely on a holder
    that has crashed and never released.

    Release does a plain GET-then-DEL (not an atomic Lua compare-and-delete)
    to keep the Redis surface to commands the in-memory test fake can
    trivially implement. There's a narrow window where a lock could expire
    and be re-acquired by someone else between the GET and the DEL, in
    which case this could delete a lock we no longer own — acceptable here
    since the mutex only guards a brief synchronous section per request,
    not the actual repo analysis.
    """

    def __init__(
        self, key_prefix: str = "repo_lock", ttl_seconds: int = 30, redis_client: Redis | None = None
    ) -> None:
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._redis_client = redis_client

    def _client(self) -> Redis:
        return self._redis_client or get_redis_client()

    def _key(self, name: str) -> str:
        return f"{self._key_prefix}:{name}"

    def _acquire_sync(self, key: str, token: str) -> bool:
        client = self._client()
        return bool(client.set(key, token, nx=True, ex=self._ttl_seconds))

    def _release_sync(self, key: str, token: str) -> None:
        client = self._client()
        if client.get(key) == token:
            client.delete(key)

    async def acquire(self, name: str, timeout: float = 20.0, poll_interval: float = 0.2) -> str | None:
        key = self._key(name)
        token = uuid.uuid4().hex
        deadline = time.monotonic() + timeout
        while True:
            if await asyncio.to_thread(self._acquire_sync, key, token):
                return token
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(poll_interval)

    async def release(self, name: str, token: str) -> None:
        key = self._key(name)
        await asyncio.to_thread(self._release_sync, key, token)