"""Redis-backed session storage for production use."""

from __future__ import annotations

import json
from typing import cast

from redis import Redis
from redis.exceptions import WatchError

from src.services.session_store import ChatMessage, new_session_id, validate_session_id


class RedisSessionStore:
    """Persist session histories in Redis with optional TTL."""

    backend_name = "redis"
    transaction_retries = 8

    def __init__(
        self,
        redis_url: str,
        max_history: int = 20,
        ttl_seconds: int = 86400,
        client: Redis | None = None,
        key_prefix: str = "nenebot:session:",
        language_key_prefix: str = "nenebot:session-lang:",
    ) -> None:
        if max_history < 2:
            raise ValueError("max_history must retain at least one user/assistant turn.")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be non-negative.")
        self.client = (
            client if client is not None else Redis.from_url(redis_url, decode_responses=True)
        )
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.language_key_prefix = language_key_prefix

    def get_or_create(self, session_id: str | None) -> str:
        return new_session_id() if session_id is None else validate_session_id(session_id)

    def get_history(self, session_id: str) -> list[ChatMessage]:
        raw = self.client.get(self._key(session_id))
        return self._decode_history(raw)

    @staticmethod
    def _decode_history(raw: object) -> list[ChatMessage]:
        if not raw or not isinstance(raw, (str, bytes, bytearray)):
            return []
        loaded = json.loads(raw)
        return cast("list[ChatMessage]", loaded) if isinstance(loaded, list) else []

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        key = self._key(session_id)
        for _ in range(self.transaction_retries):
            try:
                with self.client.pipeline() as pipeline:
                    pipeline.watch(key)  # type: ignore[no-untyped-call]
                    history = self._decode_history(pipeline.get(key))
                    history.extend(
                        [
                            {"role": "user", "content": user_msg},
                            {"role": "assistant", "content": assistant_msg},
                        ]
                    )
                    if len(history) > self.max_history:
                        history = history[-self.max_history :]

                    pipeline.multi()
                    pipeline.set(key, json.dumps(history, ensure_ascii=False))
                    if self.ttl_seconds > 0:
                        pipeline.expire(key, self.ttl_seconds)
                    pipeline.execute()
                return
            except WatchError:
                continue

        raise RuntimeError("Could not update session history after concurrent Redis writes.")

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
        return f"{self.key_prefix}{validate_session_id(session_id)}"

    def _language_key(self, session_id: str) -> str:
        return f"{self.language_key_prefix}{validate_session_id(session_id)}"

    def ping(self) -> bool:
        """Expose backend liveness checks for health reporting."""
        return bool(self.client.ping())
