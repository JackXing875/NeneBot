import asyncio
from collections.abc import AsyncIterator

import pytest

from src.core.exceptions import LLMProviderUnavailableError, LLMTimeoutError
from src.infrastructure.llm_resilience import resilient_stream


async def collect(stream: AsyncIterator[str]) -> str:
    chunks: list[str] = []
    async for chunk in stream:
        chunks.append(chunk)
    return "".join(chunks)


def test_resilient_stream_returns_content(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 1)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 1.0)

    async def stream_factory() -> AsyncIterator[str]:
        yield "hello"
        yield " world"

    result = asyncio.run(
        collect(
            resilient_stream(
                stream_factory,
                provider_name="fake",
                model_name="fake-model",
            )
        )
    )

    assert result == "hello world"


def test_resilient_stream_times_out(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 0)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 0.01)

    async def stream_factory() -> AsyncIterator[str]:
        await asyncio.sleep(0.05)
        yield "late"

    with pytest.raises(LLMTimeoutError):
        asyncio.run(
            collect(
                resilient_stream(
                    stream_factory,
                    provider_name="fake",
                    model_name="fake-model",
                )
            )
        )


def test_resilient_stream_raises_unavailable_after_retry(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 1)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 0.5)

    async def stream_factory() -> AsyncIterator[str]:
        raise RuntimeError("provider down")
        yield "unreachable"

    with pytest.raises(LLMProviderUnavailableError):
        asyncio.run(
            collect(
                resilient_stream(
                    stream_factory,
                    provider_name="fake",
                    model_name="fake-model",
                )
            )
        )
