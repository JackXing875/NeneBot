"""Custom exception classes for Persona Studio."""


class PersonaStudioError(Exception):
    """Base exception for explicit application errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "persona_studio_error",
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class VectorStoreError(PersonaStudioError):
    """Raised when vector database operations fail."""


class LLMInferenceError(PersonaStudioError):
    """Raised when the LLM service (Ollama) returns an error."""


class RateLimitExceededError(PersonaStudioError):
    """Raised when a caller exceeds the configured request budget."""

    def __init__(self, message: str = "Too many requests.") -> None:
        super().__init__(message, code="rate_limited", status_code=429)


class AuthenticationError(PersonaStudioError):
    """Raised when a protected API is accessed without valid credentials."""

    def __init__(self, message: str = "Valid API token required.") -> None:
        super().__init__(message, code="auth_required", status_code=401)


class AuthorizationError(PersonaStudioError):
    """Raised when a caller lacks the required permission scope."""

    def __init__(self, message: str = "API token lacks required scope.") -> None:
        super().__init__(message, code="forbidden", status_code=403)


class LLMTimeoutError(LLMInferenceError):
    """Raised when the provider does not answer in time."""

    def __init__(self, message: str = "LLM provider timed out.") -> None:
        super().__init__(message, code="llm_timeout", status_code=504)


class LLMProviderUnavailableError(LLMInferenceError):
    """Raised when the provider fails after retries are exhausted."""

    def __init__(self, message: str = "LLM provider unavailable.") -> None:
        super().__init__(message, code="llm_unavailable", status_code=503)
