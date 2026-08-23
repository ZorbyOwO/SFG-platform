from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from ..errors import ApiError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = monotonic()
        events = self._events[key]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            raise ApiError(429, "rate_limit_reached", "Too many attempts. Wait before trying again.")
        events.append(now)
