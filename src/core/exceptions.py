"""Custom exception classes for the NeneBot application."""


class NeneBotError(Exception):
    """Base exception for all NeneBot related errors."""


class VectorStoreError(NeneBotError):
    """Raised when vector database operations fail."""


class LLMInferenceError(NeneBotError):
    """Raised when the LLM service (Ollama) returns an error."""
