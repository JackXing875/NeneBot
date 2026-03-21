"""Async Ollama client using /api/chat with streaming support."""

import json
import logging
from typing import AsyncIterator, Dict, List

import httpx

from src.core.config import settings
from src.infrastructure.llm_base import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Async client for Ollama's /api/chat endpoint (local development)."""

    provider_name = "ollama"

    def __init__(self) -> None:
        self.chat_endpoint = f"{settings.ollama_base_url}/api/chat"
        self.model_name = settings.llm_model_name
        self._options = {"temperature": 0.7, "top_p": 0.9}
        logger.info(f"OllamaClient initialized: model={self.model_name}")

    async def chat_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncIterator[str]:
        """Yields response content chunks from Ollama's streaming API."""
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
