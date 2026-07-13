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


def test_resilient_stream_yields_before_provider_finishes(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 0)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 1.0)

    async def scenario() -> tuple[str, str]:
        release_second_chunk = asyncio.Event()

        async def stream_factory() -> AsyncIterator[str]:
            yield "first"
            await release_second_chunk.wait()
            yield " second"

        stream = resilient_stream(
            stream_factory,
            provider_name="fake",
            model_name="fake-model",
        )
        first = await asyncio.wait_for(anext(stream), timeout=0.1)
        release_second_chunk.set()
        remainder = await collect(stream)
        return first, remainder

    first, remainder = asyncio.run(scenario())

    assert first == "first"
    assert remainder == " second"


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


def test_resilient_stream_does_not_retry_after_first_chunk(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 2)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 0.5)
    calls = 0

    async def stream_factory() -> AsyncIterator[str]:
        nonlocal calls
        calls += 1
        yield "partial"
        raise RuntimeError("connection dropped")

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

    assert calls == 1
