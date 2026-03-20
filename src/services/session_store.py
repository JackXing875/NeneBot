"""In-memory session store for multi-turn conversation memory."""

import uuid
from collections import defaultdict
from typing import Dict, List


class SessionStore:
    """Manages per-session conversation history (short-term memory).

    Each session holds a sliding window of ChatML messages (user + assistant turns).
    Sessions live in-process memory; they reset on server restart.
    For persistence across restarts, replace with Redis/SQLite backend.
    """

    def __init__(self, max_history: int = 20) -> None:
        self._sessions: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self.max_history = max_history

    def get_or_create(self, session_id: str | None) -> str:
        """Returns the given session_id, or creates a fresh UUID if None."""
        return session_id if session_id else str(uuid.uuid4())

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Returns a copy of the message history for the session."""
        return list(self._sessions[session_id])

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Appends a user+assistant turn and trims to max_history."""
        buf = self._sessions[session_id]
        buf.append({"role": "user", "content": user_msg})
        buf.append({"role": "assistant", "content": assistant_msg})
        if len(buf) > self.max_history:
            self._sessions[session_id] = buf[-self.max_history :]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
