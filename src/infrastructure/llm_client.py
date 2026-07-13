"""Async Ollama client using /api/chat with streaming support."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient
from src.infrastructure.llm_resilience import resilient_stream

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Async client for Ollama's /api/chat endpoint (local development)."""

    provider_name = "ollama"

    def __init__(self) -> None:
        self.chat_endpoint = f"{settings.ollama_base_url}/api/chat"
        self.model_name = settings.llm_model_name
        self._options = {
            "temperature": settings.llm_temperature_ollama,
            "top_p": settings.llm_top_p_ollama,
        }
        logger.info(f"OllamaClient initialized: model={self.model_name}")

    async def chat_stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Yields response content chunks from Ollama's streaming API."""

        async def stream_factory() -> AsyncIterator[str]:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": self._options,
            }
            # trust_env=False prevents httpx from picking up http_proxy / HTTP_PROXY
            # env vars, which would route localhost Ollama requests through a proxy
            # and cause 502 Bad Gateway errors.
            async with httpx.AsyncClient(trust_env=False) as client:
                async with client.stream(
                    "POST",
                    self.chat_endpoint,
                    json=payload,
                    timeout=settings.llm_timeout_seconds,
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

        async for chunk in resilient_stream(
            stream_factory,
            provider_name=self.provider_name,
            model_name=self.model_name,
        ):
            yield chunk
