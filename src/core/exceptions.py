"""Custom exception classes for the NeneBot application."""


class NeneBotError(Exception):
    """Base exception for all NeneBot related errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "nenebot_error",
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class VectorStoreError(NeneBotError):
    """Raised when vector database operations fail."""


class LLMInferenceError(NeneBotError):
    """Raised when the LLM service (Ollama) returns an error."""
