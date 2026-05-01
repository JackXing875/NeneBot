"""Abstract base class for all LLM clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseLLMClient(ABC):
    """Defines the common interface for all LLM provider clients.

    Implementing a new provider only requires overriding `chat_stream`.
    The non-streaming `chat` method is derived automatically.
    """

    @abstractmethod
    def chat_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        """Yield response tokens one by one."""
        ...

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """Collect all streamed tokens into a single string."""
        chunks: list[str] = []
        async for chunk in self.chat_stream(messages):
            chunks.append(chunk)
        return "".join(chunks)
