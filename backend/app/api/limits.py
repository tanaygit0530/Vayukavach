"""Per-client token buckets for endpoints that cost something (LLM calls, SMS)."""

import threading
import time

from fastapi import Request


def client_key(request: Request) -> str:
    return request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )


class Bucket:
    """`capacity` requests at once, refilled at `capacity` per `per_seconds`."""

    def __init__(self, capacity: int, per_seconds: float):
        self.capacity, self.rate = capacity, capacity / per_seconds
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            ok = tokens >= 1
            self._state[key] = (tokens - 1 if ok else tokens, now)
            return ok

    def clear(self) -> None:
        with self._lock:
            self._state.clear()
