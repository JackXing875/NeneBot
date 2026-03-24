"""Session storage abstractions and in-memory implementation."""

import uuid
from collections import defaultdict
from typing import Dict, List, Protocol

ChatMessage = Dict[str, str]


class SessionStore(Protocol):
    """Interface for per-session chat history storage."""

    backend_name: str

    def get_or_create(self, session_id: str | None) -> str:
        """Return an existing session id or create a new one."""

    def get_history(self, session_id: str) -> List[ChatMessage]:
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
        self._sessions: Dict[str, List[ChatMessage]] = defaultdict(list)
        self._language_preferences: Dict[str, str] = {}
        self.max_history = max_history

    def get_or_create(self, session_id: str | None) -> str:
        return session_id if session_id else str(uuid.uuid4())

    def get_history(self, session_id: str) -> List[ChatMessage]:
        return list(self._sessions[session_id])

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        buf = self._sessions[session_id]
        buf.append({"role": "user", "content": user_msg})
        buf.append({"role": "assistant", "content": assistant_msg})
        if len(buf) > self.max_history:
            self._sessions[session_id] = buf[-self.max_history :]

    def get_preferred_language(self, session_id: str) -> str | None:
        return self._language_preferences.get(session_id)

    def set_preferred_language(self, session_id: str, language: str | None) -> None:
        if language is None:
            self._language_preferences.pop(session_id, None)
            return
        self._language_preferences[session_id] = language

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._language_preferences.pop(session_id, None)
