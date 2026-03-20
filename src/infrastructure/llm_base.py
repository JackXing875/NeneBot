"""Abstract base class for all LLM clients."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List


class BaseLLMClient(ABC):
    """Defines the common interface for all LLM provider clients.

    Implementing a new provider only requires overriding `chat_stream`.
    The non-streaming `chat` method is derived automatically.
    """

    @abstractmethod
    async def chat_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Yield response tokens one by one."""
        ...

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Collect all streamed tokens into a single string."""
        chunks: List[str] = []
        async for chunk in self.chat_stream(messages):
            chunks.append(chunk)
        return "".join(chunks)
