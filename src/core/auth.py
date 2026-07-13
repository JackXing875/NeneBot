"""Lightweight API token authentication helpers for protected routes."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from secrets import compare_digest

from fastapi import Request

from src.core.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.metrics import auth_failures_total

DEFAULT_AUTH_SCOPES = frozenset({"chat", "ops"})


@dataclass(frozen=True)
class AuthIdentity:
    name: str
    token: str
    scopes: frozenset[str]


def _normalize_scopes(scopes: list[str] | tuple[str, ...] | set[str] | None) -> frozenset[str]:
    if not scopes:
        return DEFAULT_AUTH_SCOPES
    return frozenset(scope.strip() for scope in scopes if scope.strip()) or DEFAULT_AUTH_SCOPES


def _parse_env_identity(raw: str, idx: int) -> AuthIdentity | None:
    if ":" in raw:
        left, token = raw.split(":", 1)
        token = token.strip()
        if not token:
            return None
        if "|" in left:
            name, scopes_raw = left.split("|", 1)
            scopes = [scope.strip() for scope in scopes_raw.split(",")]
        else:
            name = left
            scopes = []
        return AuthIdentity(
            name=name.strip() or f"token-{idx}",
            token=token,
            scopes=_normalize_scopes(scopes),
        )

    return AuthIdentity(
        name=f"token-{idx}",
        token=raw,
        scopes=DEFAULT_AUTH_SCOPES,
    )


def _load_registry_identities() -> list[AuthIdentity]:
    registry_path = Path(settings.api_auth_registry_path)
    if not registry_path.exists():
        return []

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []

    identities: list[AuthIdentity] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        token = str(item.get("token", "")).strip()
        if not token:
            continue
        name = str(item.get("name", "")).strip() or f"registry-token-{idx}"
        scopes_raw = item.get("scopes")
        scopes = scopes_raw if isinstance(scopes_raw, list) else []
        identities.append(
            AuthIdentity(
                name=name,
                token=token,
                scopes=_normalize_scopes(scopes),
            )
        )
    return identities


def configured_auth_identities() -> list[AuthIdentity]:
    identities: list[AuthIdentity] = []
    for idx, item in enumerate(settings.api_auth_tokens.split(","), start=1):
        raw = item.strip()
        if not raw:
            continue

        identity = _parse_env_identity(raw, idx)
        if identity is not None:
            identities.append(identity)

    return identities + _load_registry_identities()


def auth_enabled() -> bool:
    """Return whether authentication enforcement was explicitly enabled.

    Configuration completeness must not influence this result: when auth is
    enabled without any usable identities, requests are rejected rather than
    silently falling back to unauthenticated access.
    """
    return settings.api_auth_enabled


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


def validate_api_token(token: str | None) -> AuthIdentity | None:
    if token is None:
        return None

    for identity in configured_auth_identities():
        if compare_digest(token, identity.token):
            return identity
    return None


def require_api_auth(request: Request) -> None:
    """Enforce token auth when enabled and annotate request state for audit logs."""
    if not auth_enabled():
        return

    matched = validate_api_token(extract_api_token(request))
    if matched is None:
        auth_failures_total.inc(reason="invalid_token")
        raise AuthenticationError()

    request.state.auth_subject = matched.name
    request.state.auth_scopes = sorted(matched.scopes)


def require_api_scope(scope: str) -> Callable[[Request], Awaitable[None]]:
    """Return a FastAPI dependency that enforces auth plus a named scope."""

    async def _dependency(request: Request) -> None:
        if not auth_enabled():
            return

        require_api_auth(request)
        scopes = set(getattr(request.state, "auth_scopes", []))
        if scope not in scopes:
            auth_failures_total.inc(reason="insufficient_scope", required_scope=scope)
            raise AuthorizationError(f"API token lacks required scope: {scope}.")

    return _dependency
