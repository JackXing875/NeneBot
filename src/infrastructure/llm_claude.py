"""Claude API client (via Anthropic SDK)."""

import logging
from typing import AsyncIterator, Dict, List, cast

import anthropic
from anthropic.types import MessageParam

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.llm_resilience import resilient_stream

logger = logging.getLogger(__name__)


class ClaudeClient(BaseLLMClient):
    """Streams responses from Claude via the Anthropic Messages API.

    Claude separates the system prompt from the messages array, so we
    extract it here before forwarding to the API.
    """

    provider_name = "claude"

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model_name
        logger.info(f"ClaudeClient initialized with model={self.model}")

    async def chat_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncIterator[str]:
        async def stream_factory() -> AsyncIterator[str]:
            system_content = ""
            chat_messages: List[Dict[str, str]] = []
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    chat_messages.append(msg)

            async with self._client.messages.stream(
                model=self.model,
                max_tokens=512,
                system=system_content,
                messages=cast(List[MessageParam], chat_messages),
                temperature=1.0,  # anthropic sdk controls creativity differently
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        async for chunk in resilient_stream(
            stream_factory,
            provider_name=self.provider_name,
            model_name=self.model,
        ):
            yield chunk
