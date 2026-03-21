"""Per-request context helpers used by logging and error responses."""

from contextvars import ContextVar, Token

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the current request id or '-' outside a request scope."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> Token[str]:
    """Bind a request id to the current context."""
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request context."""
    _request_id_ctx.reset(token)
