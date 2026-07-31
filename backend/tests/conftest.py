import time

import pytest


class InMemoryRedis:
    """A minimal dict-based Redis-like stub for tests.

    Supports `incr`, `expire`, `get`, sorted-set helpers, and a test-only `advance`
    to move time forward. Keys expire based on the TTL set with `expire`.
    """

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, float] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}
        # internal clock (float seconds since epoch) so tests can advance time
        self._now = time.time()

    def _is_expired(self, key: str) -> bool:
        exp = self.expirations.get(key)
        if exp is None:
            return False
        return self._now >= exp

    def incr(self, key: str) -> int:
        if self._is_expired(key):
            self.values.pop(key, None)
            self.expirations.pop(key, None)

        val = self.values.get(key, 0) + 1
        self.values[key] = val
        return val

    def expire(self, key: str, ttl: int) -> bool:
        # set expiration relative to the internal clock
        self.expirations[key] = self._now + ttl
        return True

    def get(self, key: str):
        if self._is_expired(key):
            self.values.pop(key, None)
            self.expirations.pop(key, None)
            return None

        value = self.values.get(key)
        return None if value is None else str(value)

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        entries = self.sorted_sets.setdefault(key, {})
        for member, score in mapping.items():
            entries[str(member)] = float(score)
        return len(mapping)

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        entries = self.sorted_sets.get(key)
        if not entries:
            return 0

        to_remove = [member for member, score in entries.items() if score <= max_score]
        for member in to_remove:
            entries.pop(member, None)
        return len(to_remove)

    def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))

    def zrem(self, key: str, member: str) -> int:
        entries = self.sorted_sets.get(key)
        if not entries or str(member) not in entries:
            return 0
        del entries[str(member)]
        return 1

    def set(self, key: str, value, nx: bool = False, ex: int | None = None) -> bool:
        if nx and not self._is_expired(key) and key in self.values:
            return False

        self.values[key] = value
        if ex is not None:
            self.expire(key, ex)
        else:
            self.expirations.pop(key, None)
        return True

    def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.expirations.pop(key, None)
        return 1 if existed else 0

    # test helper to move the internal clock forward
    def advance(self, seconds: int) -> None:
        self._now += seconds


@pytest.fixture
def fake_redis() -> InMemoryRedis:
    return InMemoryRedis()