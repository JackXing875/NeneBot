"""Client for interacting with the local Ollama LLM API.

This module provides an asynchronous interface to send generated prompts
to a local Ollama instance and retrieve the text responses.
"""

import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client to interact with the Ollama REST API."""

    def __init__(self) -> None:
        """Initializes the Ollama client with settings."""
        self.base_url = settings.ollama_base_url
        self.model_name = settings.llm_model_name
        self.generate_endpoint = f"{self.base_url}/api/generate"

    async def generate(self, prompt: str) -> str:
        """Sends a prompt to the Ollama API and returns the generated text.

        Args:
            prompt: The fully constructed prompt string (including context).

        Returns:
            The generated response string from the LLM.

        Raises:
            httpx.HTTPError: If the connection to Ollama fails.
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            # Set temperature low to make Ningning stick closely to the reference context
            "options": {"temperature": 0.3, "top_p": 0.85},
        }

        logger.info(f"Sending request to Ollama ({self.model_name})...")

        try:
            # Using a generous timeout as local LLM inference can take a few seconds
            async with httpx.AsyncClient() as client:
                response = await client.post(self.generate_endpoint, json=payload, timeout=60.0)
                response.raise_for_status()

                result = response.json()
                return result.get("response", "").strip()
        except httpx.HTTPError as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return "（宁宁正在思考中，但大脑连接断开了...请检查 Ollama 是否运行）"
