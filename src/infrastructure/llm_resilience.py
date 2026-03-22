"""Shared timeout and retry handling for provider streaming calls."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import httpx

from src.core.config import settings
from src.core.exceptions import LLMProviderUnavailableError, LLMTimeoutError
from src.core.observability import now_ms

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    provider_name: str,
    model_name: str | None,
) -> T:
    """Run an async operation with timeout and bounded retries."""
    last_error: Exception | None = None
    for attempt in range(1, settings.llm_max_retries + 2):
        started_at = now_ms()
        try:
            return await asyncio.wait_for(operation(), timeout=settings.llm_timeout_seconds)
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning(
                "llm_attempt_timeout",
                extra={
                    "event": "llm_attempt_timeout",
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "duration_ms": round(now_ms() - started_at, 2),
                },
            )
        except (httpx.HTTPError, Exception) as exc:
            last_error = exc
            logger.warning(
                "llm_attempt_failed",
                extra={
                    "event": "llm_attempt_failed",
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "duration_ms": round(now_ms() - started_at, 2),
                },
            )
        if attempt <= settings.llm_max_retries:
            await asyncio.sleep(0.25 * attempt)

    if isinstance(last_error, asyncio.TimeoutError):
        raise LLMTimeoutError() from last_error
    raise LLMProviderUnavailableError(str(last_error) if last_error else None) from last_error


async def resilient_stream(
    factory: Callable[[], AsyncIterator[str]],
    *,
    provider_name: str,
    model_name: str | None,
) -> AsyncIterator[str]:
    """Open and consume a provider stream with timeout/retry handling."""
    queue: list[str] = await with_retries(
        lambda: _consume_stream(factory),
        provider_name=provider_name,
        model_name=model_name,
    )
    for chunk in queue:
        yield chunk


async def _consume_stream(factory: Callable[[], AsyncIterator[str]]) -> list[str]:
    """Consume the provider stream into memory after a successful call."""
    chunks: list[str] = []
    async for chunk in factory():
        chunks.append(chunk)
    return chunks
