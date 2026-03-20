"""Claude API client (via Anthropic SDK)."""

import logging
from typing import AsyncGenerator, Dict, List

import anthropic

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient

logger = logging.getLogger(__name__)


class ClaudeClient(BaseLLMClient):
    """Streams responses from Claude via the Anthropic Messages API.

    Claude separates the system prompt from the messages array, so we
    extract it here before forwarding to the API.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model_name
        logger.info(f"ClaudeClient initialized with model={self.model}")

    async def chat_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        system_content = ""
        chat_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                chat_messages.append(msg)

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=512,
                system=system_content,
                messages=chat_messages,
                temperature=1.0,  # anthropic sdk controls creativity differently
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            yield "（宁宁的思绪断开了……请检查 Anthropic API Key 是否正确）"
