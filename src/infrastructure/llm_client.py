"""Async Ollama client using /api/chat with streaming support."""

import json
import logging
from typing import AsyncGenerator, Dict, List

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async client for Ollama's /api/chat endpoint.

    Supports:
    - Token-level streaming via chat_stream() (for SSE endpoints)
    - Full-response await via chat() (fallback / testing)
    """

    def __init__(self) -> None:
        self.chat_endpoint = f"{settings.ollama_base_url}/api/chat"
        self.model_name = settings.llm_model_name
        self._options = {"temperature": 0.3, "top_p": 0.85}

    async def chat_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Yields response content chunks from Ollama's streaming API."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": self._options,
        }
        try:
            # trust_env=False prevents httpx from picking up http_proxy / HTTP_PROXY
            # env vars, which would route localhost Ollama requests through a proxy
            # and cause 502 Bad Gateway errors.
            async with httpx.AsyncClient(trust_env=False) as client:
                async with client.stream(
                    "POST", self.chat_endpoint, json=payload, timeout=120.0
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if not data.get("done"):
                                content = data.get("message", {}).get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            yield "（宁宁的思绪断开了……请检查 Ollama 是否在运行）"

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Non-streaming convenience wrapper; collects all chunks into a string."""
        chunks: List[str] = []
        async for chunk in self.chat_stream(messages):
            chunks.append(chunk)
        return "".join(chunks)
