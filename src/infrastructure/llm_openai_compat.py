"""OpenAI-compatible API client (DeepSeek, Qwen-API, etc.)."""

import logging
from typing import AsyncIterator, Dict, List, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAICompatClient(BaseLLMClient):
    """Works with any OpenAI-compatible endpoint.

    Tested with DeepSeek V3 (https://api.deepseek.com).
    Switch providers by changing OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY.
    """

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
        self, messages: List[Dict[str, str]]
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=cast(List[ChatCompletionMessageParam], messages),
            stream=True,
            temperature=0.7,
            max_tokens=512,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
