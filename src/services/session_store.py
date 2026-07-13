"""Session storage abstractions and in-memory implementation."""

from __future__ import annotations

import re
import uuid
from typing import Protocol

ChatMessage = dict[str, str]
MAX_SESSION_ID_LENGTH = 128
TELEGRAM_SESSION_PATTERN = re.compile(r"^telegram:-?[1-9][0-9]*$")


def validate_session_id(session_id: str, *, allow_telegram: bool = True) -> str:
    """Validate a bounded, Redis-key-safe session identifier."""
    if not session_id or session_id != session_id.strip():
        raise ValueError("Session ID must not be empty or contain surrounding whitespace.")
    if len(session_id) > MAX_SESSION_ID_LENGTH:
        raise ValueError(f"Session ID must be at most {MAX_SESSION_ID_LENGTH} characters.")
    is_telegram_namespace = session_id.lower().startswith("telegram:")
    if is_telegram_namespace:
        if not allow_telegram:
            raise ValueError("The telegram session namespace is reserved for internal use.")
        if TELEGRAM_SESSION_PATTERN.fullmatch(session_id) is None:
            raise ValueError("Invalid internal Telegram session ID.")
        return session_id

    try:
        parsed_id = uuid.UUID(session_id)
    except ValueError as exc:
        raise ValueError("Session ID must be a canonical UUID v4.") from exc
    if parsed_id.version != 4 or str(parsed_id) != session_id:
        raise ValueError("Session ID must be a canonical UUID v4.")
    return session_id


def new_session_id() -> str:
    """Return a server-generated session identifier."""
    return str(uuid.uuid4())


class SessionStore(Protocol):
    """Interface for per-session chat history storage."""

    backend_name: str

    def get_or_create(self, session_id: str | None) -> str:
        """Return an existing session id or create a new one."""

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """Return a copy of the persisted message history."""

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Append a full user+assistant turn."""

    def get_preferred_language(self, session_id: str) -> str | None:
        """Return the stored reply-language preference for the session."""

    def set_preferred_language(self, session_id: str, language: str | None) -> None:
        """Persist or clear the session-level reply-language preference."""

    def clear(self, session_id: str) -> None:
        """Delete all history for a session."""


class InMemorySessionStore:
    """Process-local session store for development and fallback use."""

    backend_name = "memory"

    def __init__(self, max_history: int = 20) -> None:
        if max_history < 2:
            raise ValueError("max_history must retain at least one user/assistant turn.")
        self._sessions: dict[str, list[ChatMessage]] = {}
        self._language_preferences: dict[str, str] = {}
        self.max_history = max_history

    def get_or_create(self, session_id: str | None) -> str:
        return new_session_id() if session_id is None else validate_session_id(session_id)

    def get_history(self, session_id: str) -> list[ChatMessage]:
        validated_id = validate_session_id(session_id)
        return list(self._sessions.get(validated_id, []))

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        validated_id = validate_session_id(session_id)
        buf = self._sessions.setdefault(validated_id, [])
        buf.append({"role": "user", "content": user_msg})
        buf.append({"role": "assistant", "content": assistant_msg})
        if len(buf) > self.max_history:
            self._sessions[validated_id] = buf[-self.max_history :]

    def get_preferred_language(self, session_id: str) -> str | None:
        return self._language_preferences.get(validate_session_id(session_id))

    def set_preferred_language(self, session_id: str, language: str | None) -> None:
        validated_id = validate_session_id(session_id)
        if language is None:
            self._language_preferences.pop(validated_id, None)
            return
        self._language_preferences[validated_id] = language

    def clear(self, session_id: str) -> None:
        validated_id = validate_session_id(session_id)
        self._sessions.pop(validated_id, None)
        self._language_preferences.pop(validated_id, None)
