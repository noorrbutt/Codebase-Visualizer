from __future__ import annotations

import asyncio
import time
import uuid

from app.services.redis_client import get_redis_client

# Atomically: drop expired slots, then admit a new one only if the live
# count is still under the cap. Doing this in one Lua script (instead of
# ZCARD-then-ZADD from Python) closes the race where two callers both pass
# the check before either has added its member.
_ACQUIRE_SEMAPHORE_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local max_slots = tonumber(ARGV[3])
local token = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - ttl)
local count = redis.call('ZCARD', key)
if count < max_slots then
    redis.call('ZADD', key, now, token)
    redis.call('EXPIRE', key, ttl)
    return 1
else
    return 0
end
"""

# Only delete a mutex key if it still holds the token we set — otherwise we
# might delete a lock that expired and was already re-acquired by someone else.
_RELEASE_MUTEX_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class RedisConcurrencyGate:
    """Distributed cap on concurrently running repo analyses.

    Backed by a Redis sorted set used as an expiring semaphore: each
    acquired slot is a member scored by its acquisition time. If a worker
    crashes or a Render instance sleeps mid-analysis without releasing its
    slot, that slot ages out after `slot_ttl_seconds` instead of leaking
    the counter forever (which a plain Redis INCR/DECR counter would do).
    """

    KEY = "repo_analysis:semaphore"

    def __init__(self, max_concurrent_analyses: int, slot_ttl_seconds: int = 180) -> None:
        self._max_concurrent_analyses = max_concurrent_analyses
        self._slot_ttl_seconds = slot_ttl_seconds
        self._held_token: str | None = None

    def _try_acquire_sync(self) -> str | None:
        client = get_redis_client()
        now = time.time()
        token = uuid.uuid4().hex
        acquired = client.eval(
            _ACQUIRE_SEMAPHORE_LUA,
            1,
            self.KEY,
            now,
            self._slot_ttl_seconds,
            self._max_concurrent_analyses,
            token,
        )
        return token if acquired else None

    def _release_sync(self, token: str) -> None:
        client = get_redis_client()
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
    """

    def __init__(self, key_prefix: str = "repo_lock", ttl_seconds: int = 30) -> None:
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def _key(self, name: str) -> str:
        return f"{self._key_prefix}:{name}"

    def _acquire_sync(self, key: str, token: str) -> bool:
        client = get_redis_client()
        return bool(client.set(key, token, nx=True, ex=self._ttl_seconds))

    def _release_sync(self, key: str, token: str) -> None:
        client = get_redis_client()
        client.eval(_RELEASE_MUTEX_LUA, 1, key, token)

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