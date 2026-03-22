import asyncio

import pytest
from fastapi import Request
from fastapi.responses import Response

from src.core.exceptions import RateLimitExceededError
from src.core.rate_limit import InMemoryRateLimiter, RateLimitMiddleware


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    limiter.check("client-1")
    limiter.check("client-1")
    with pytest.raises(RateLimitExceededError):
        limiter.check("client-1")


def test_rate_limit_middleware_returns_429() -> None:
    middleware = RateLimitMiddleware(
        app=lambda scope, receive, send: None,
        limiter=InMemoryRateLimiter(limit=1, window_seconds=60),
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/test",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "http_version": "1.1",
        }
    )

    async def call_next(_: Request) -> Response:
        return Response(content=b"ok", status_code=200)

    first = asyncio.run(middleware.dispatch(request, call_next))
    assert first.status_code == 200

    with pytest.raises(RateLimitExceededError):
        asyncio.run(middleware.dispatch(request, call_next))
