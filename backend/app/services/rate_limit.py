from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock


class IPRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, ip_address: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds

        with self._lock:
            request_times = self._requests[ip_address]
            while request_times and request_times[0] <= window_start:
                request_times.popleft()

            if len(request_times) >= self.max_requests:
                return False

            request_times.append(now)
            return True
