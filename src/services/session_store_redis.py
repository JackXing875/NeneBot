"""Redis-backed session storage for production use."""

import json
import uuid
from typing import List

from redis import Redis

from src.services.session_store import ChatMessage


class RedisSessionStore:
    """Persist session histories in Redis with optional TTL."""

    backend_name = "redis"

    def __init__(
        self,
        redis_url: str,
        max_history: int = 20,
        ttl_seconds: int = 86400,
        client: Redis | None = None,
        key_prefix: str = "nenebot:session:",
        language_key_prefix: str = "nenebot:session-lang:",
    ) -> None:
        self.client = (
            client
            if client is not None
            else Redis.from_url(redis_url, decode_responses=True)
        )
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.language_key_prefix = language_key_prefix

    def get_or_create(self, session_id: str | None) -> str:
        return session_id if session_id else str(uuid.uuid4())

    def get_history(self, session_id: str) -> List[ChatMessage]:
        raw = self.client.get(self._key(session_id))
        if not raw:
            return []
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, list) else []

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        history = self.get_history(session_id)
        history.extend(
            [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ]
        )
        if len(history) > self.max_history:
            history = history[-self.max_history :]
        self.client.set(self._key(session_id), json.dumps(history, ensure_ascii=False))
        if self.ttl_seconds > 0:
            self.client.expire(self._key(session_id), self.ttl_seconds)

    def get_preferred_language(self, session_id: str) -> str | None:
        language = self.client.get(self._language_key(session_id))
        return language if isinstance(language, str) and language else None

    def set_preferred_language(self, session_id: str, language: str | None) -> None:
        key = self._language_key(session_id)
        if language is None:
            self.client.delete(key)
            return
        self.client.set(key, language)
        if self.ttl_seconds > 0:
            self.client.expire(key, self.ttl_seconds)

    def clear(self, session_id: str) -> None:
        self.client.delete(self._key(session_id))
        self.client.delete(self._language_key(session_id))

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"

    def _language_key(self, session_id: str) -> str:
        return f"{self.language_key_prefix}{session_id}"

    def ping(self) -> bool:
        """Expose backend liveness checks for health reporting."""
        return bool(self.client.ping())
