"""Shared timeout and retry handling for provider streaming calls."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import httpx

from src.core.config import settings
from src.core.exceptions import LLMProviderUnavailableError, LLMTimeoutError
from src.core.metrics import llm_failures_total, llm_retry_attempts_total
from src.core.observability import now_ms
from src.core.tracing import set_span_attributes, traced_span

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    provider_name: str,
    model_name: str | None,
) -> T:
    """Run an async operation with timeout and bounded retries."""
    with traced_span(
        "llm.request",
        provider_name=provider_name,
        model_name=model_name,
        max_retries=settings.llm_max_retries,
    ) as span:
        last_error: Exception | None = None
        for attempt in range(1, settings.llm_max_retries + 2):
            started_at = now_ms()
            try:
                result = await asyncio.wait_for(operation(), timeout=settings.llm_timeout_seconds)
                set_span_attributes(
                    span,
                    llm_attempt=attempt,
                    llm_duration_ms=round(now_ms() - started_at, 2),
                    llm_outcome="success",
                )
                return result
            except asyncio.TimeoutError as exc:
                last_error = exc
                llm_retry_attempts_total.inc(
                    provider_name=provider_name,
                    reason="timeout",
                    attempt=str(attempt),
                )
                logger.warning(
                    "llm_attempt_timeout",
                    extra={
                        "event": "llm_attempt_timeout",
                        "provider_name": provider_name,
                        "model_name": model_name,
                        "duration_ms": round(now_ms() - started_at, 2),
                    },
                )
                set_span_attributes(
                    span,
                    llm_attempt=attempt,
                    llm_last_error="timeout",
                )
            except (httpx.HTTPError, Exception) as exc:
                last_error = exc
                reason = "http_error" if isinstance(exc, httpx.HTTPError) else "exception"
                llm_retry_attempts_total.inc(
                    provider_name=provider_name,
                    reason=reason,
                    attempt=str(attempt),
                )
                logger.warning(
                    "llm_attempt_failed",
                    extra={
                        "event": "llm_attempt_failed",
                        "provider_name": provider_name,
                        "model_name": model_name,
                        "duration_ms": round(now_ms() - started_at, 2),
                    },
                )
                set_span_attributes(
                    span,
                    llm_attempt=attempt,
                    llm_last_error=reason,
                )
            if attempt <= settings.llm_max_retries:
                await asyncio.sleep(0.25 * attempt)

        if isinstance(last_error, asyncio.TimeoutError):
            llm_failures_total.inc(provider_name=provider_name, reason="timeout")
            set_span_attributes(span, llm_outcome="timeout")
            raise LLMTimeoutError() from last_error
        llm_failures_total.inc(provider_name=provider_name, reason="unavailable")
        set_span_attributes(span, llm_outcome="unavailable")
        raise LLMProviderUnavailableError(
            str(last_error) if last_error else "LLM provider unavailable."
        ) from last_error


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
