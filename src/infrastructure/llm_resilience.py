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
    """Yield provider chunks as they arrive with safe retry semantics.

    A provider call may be retried only before its first chunk is exposed to
    the caller.  Retrying after output has started could duplicate content, so
    later failures are surfaced immediately instead.
    """
    started = await with_retries(
        lambda: _start_stream(factory),
        provider_name=provider_name,
        model_name=model_name,
    )
    if started is None:
        return

    stream, first_chunk = started
    try:
        yield first_chunk
        while True:
            try:
                chunk = await asyncio.wait_for(
                    anext(stream),
                    timeout=settings.llm_timeout_seconds,
                )
            except StopAsyncIteration:
                return
            except asyncio.TimeoutError as exc:
                llm_failures_total.inc(provider_name=provider_name, reason="stream_timeout")
                raise LLMTimeoutError() from exc
            except Exception as exc:
                llm_failures_total.inc(provider_name=provider_name, reason="stream_interrupted")
                raise LLMProviderUnavailableError(str(exc)) from exc
            else:
                yield chunk
    finally:
        await _close_stream(stream)


async def _start_stream(
    factory: Callable[[], AsyncIterator[str]],
) -> tuple[AsyncIterator[str], str] | None:
    """Open a stream and read its first chunk without consuming the remainder."""
    stream = factory()
    try:
        first_chunk = await anext(stream)
    except StopAsyncIteration:
        await _close_stream(stream)
        return None
    except BaseException:
        await _close_stream(stream)
        raise
    return stream, first_chunk


async def _close_stream(stream: AsyncIterator[str]) -> None:
    """Close async-generator resources when the provider exposes ``aclose``."""
    close = getattr(stream, "aclose", None)
    if close is not None:
        await close()
