"""Lightweight API token authentication helpers for protected routes."""

from secrets import compare_digest

from fastapi import Request

from src.core.config import settings
from src.core.exceptions import AuthenticationError


def _configured_tokens() -> set[str]:
    return {
        token.strip()
        for token in settings.api_auth_tokens.split(",")
        if token.strip()
    }


def auth_enabled() -> bool:
    return settings.api_auth_enabled and bool(_configured_tokens())


def extract_api_token(request: Request) -> str | None:
    auth_header = request.headers.get(settings.api_auth_header_name)
    if auth_header:
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip() or None
        return auth_header.strip() or None

    x_api_key = request.headers.get("X-API-Key")
    if x_api_key:
        return x_api_key.strip() or None

    return None


def token_subject(token: str) -> str:
    if len(token) <= 8:
        return token
    return f"{token[:4]}...{token[-4:]}"

def validate_api_token(token: str | None) -> str | None:
    if token is None:
        return None

    for configured in _configured_tokens():
        if compare_digest(token, configured):
            return configured
    return None


def require_api_auth(request: Request) -> None:
    """Enforce token auth when enabled and annotate request state for audit logs."""
    if not auth_enabled():
        return

    matched = validate_api_token(extract_api_token(request))
    if matched is None:
        raise AuthenticationError()

    request.state.auth_subject = token_subject(matched)
