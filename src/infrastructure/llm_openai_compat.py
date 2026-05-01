"""OpenAI-compatible API client (DeepSeek, Qwen-API, etc.)."""

from __future__ import annotations

import logging
from typing import AsyncIterator, List, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.llm_resilience import resilient_stream

logger = logging.getLogger(__name__)


class OpenAICompatClient(BaseLLMClient):
    """Works with any OpenAI-compatible endpoint.

    Tested with DeepSeek V3 (https://api.deepseek.com).
    Switch providers by changing OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY.
    """

    provider_name = "openai_compat"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.openai_compat_api_key,
            base_url=settings.openai_compat_base_url,
        )
        self.model = settings.openai_compat_model
        logger.info(
            f"OpenAICompatClient initialized: model={self.model}, "
            f"base_url={settings.openai_compat_base_url}"
        )

    async def chat_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        async def stream_factory() -> AsyncIterator[str]:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=cast(List[ChatCompletionMessageParam], messages),
                stream=True,
                temperature=settings.llm_temperature_openai,
                max_tokens=settings.llm_max_tokens_openai,
                timeout=settings.llm_timeout_seconds,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        async for chunk in resilient_stream(
            stream_factory,
            provider_name=self.provider_name,
            model_name=self.model,
        ):
            yield chunk
