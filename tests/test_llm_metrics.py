import asyncio

import pytest

from src.core.exceptions import LLMProviderUnavailableError, LLMTimeoutError
from src.core.metrics import llm_failures_total, llm_retry_attempts_total
from src.infrastructure.llm_resilience import with_retries


async def _always_timeout() -> str:
    raise asyncio.TimeoutError()


async def _always_fail() -> str:
    raise RuntimeError("boom")


def test_with_retries_records_timeout_metrics(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 1)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 0.01)

    before_retry = dict(llm_retry_attempts_total.values)
    before_fail = dict(llm_failures_total.values)

    with pytest.raises(LLMTimeoutError):
        asyncio.run(
            with_retries(
                _always_timeout,
                provider_name="deepseek",
                model_name="deepseek-chat",
            )
        )

    assert dict(llm_retry_attempts_total.values) != before_retry
    assert dict(llm_failures_total.values) != before_fail


def test_with_retries_records_unavailable_metrics(monkeypatch) -> None:
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_max_retries", 0)
    monkeypatch.setattr("src.infrastructure.llm_resilience.settings.llm_timeout_seconds", 1.0)

    before_retry = dict(llm_retry_attempts_total.values)
    before_fail = dict(llm_failures_total.values)

    with pytest.raises(LLMProviderUnavailableError):
        asyncio.run(
            with_retries(
                _always_fail,
                provider_name="ollama",
                model_name="qwen2.5",
            )
        )

    assert dict(llm_retry_attempts_total.values) != before_retry
    assert dict(llm_failures_total.values) != before_fail
