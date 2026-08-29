"""A small, fail-fast concurrency limiter for expensive provider calls.

This is not a queue: a caller that cannot acquire a slot immediately is
rejected, not made to wait. That is a deliberate choice for a personal,
single-user service - we would rather fail one request fast and let the
user retry than silently accumulate unbounded in-memory work.
"""

from __future__ import annotations

import asyncio


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1.")
        self._max_concurrent = max_concurrent
        self._current = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._current >= self._max_concurrent:
                return False
            self._current += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            self._current = max(0, self._current - 1)
