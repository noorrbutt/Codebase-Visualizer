import time

import pytest


class InMemoryRedis:
    """A minimal dict-based Redis-like stub for tests.

    Supports `incr`, `expire`, `get`, and a test-only `advance` to move time forward.
    Keys expire based on the TTL set with `expire`.
    """

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, float] = {}
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

    # test helper to move the internal clock forward
    def advance(self, seconds: int) -> None:
        self._now += seconds


@pytest.fixture
def fake_redis() -> InMemoryRedis:
    return InMemoryRedis()
