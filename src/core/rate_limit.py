"""Simple in-process rate limiting middleware for API protection."""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import DefaultDict

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.config import settings
from src.core.exceptions import RateLimitExceededError
from src.core.metrics import rate_limit_exceeded_total


class InMemoryRateLimiter:
    """Track request timestamps per key within a rolling window."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: DefaultDict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self._buckets[key]

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.limit:
            rate_limit_exceeded_total.inc(key=key)
            raise RateLimitExceededError(
                f"Rate limit exceeded: {self.limit} requests per {self.window_seconds} seconds."
            )

        bucket.append(now)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply in-memory rate limiting to selected API paths."""

    def __init__(self, app: ASGIApp, limiter: InMemoryRateLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/v1/"):
            key = request.client.host if request.client else "unknown"
            try:
                self.limiter.check(key)
            except RateLimitExceededError as exc:
                request_id = getattr(request.state, "request_id", "-")
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "error": {
                            "code": exc.code,
                            "message": exc.message,
                            "status_code": exc.status_code,
                        },
                        "request_id": request_id,
                    },
                    headers={"Retry-After": str(self.limiter.window_seconds)},
                )
        return await call_next(request)


def build_default_rate_limiter() -> InMemoryRateLimiter:
    """Construct the configured default in-memory limiter."""
    return InMemoryRateLimiter(
        limit=settings.api_rate_limit_count,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
