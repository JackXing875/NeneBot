"""Observability helpers: structured logging and health reporting."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.request_context import get_request_id
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore


class JsonFormatter(logging.Formatter):
    """Serialize log records as compact JSON for production ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
        }

        for field in (
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "session_backend",
            "llm_provider",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def build_health_payload(
    *,
    vector_store: FaissVectorStore,
    frontend_dist_exists: bool,
    session_backend_name: str,
    session_backend_ok: bool,
    session_backend_error: str | None = None,
) -> dict[str, object]:
    """Build the standard health payload returned by `/health`."""
    llm_model = (
        settings.claude_model_name
        if settings.llm_provider == "claude"
        else settings.openai_compat_model
        if settings.llm_provider in ("deepseek", "openai")
        else settings.llm_model_name
    )
    vector_index_exists = Path(settings.vector_index_path).exists()
    knowledge_meta_exists = Path(settings.knowledge_meta_path).exists()

    payload: dict[str, object] = {
        "status": "ok" if session_backend_ok else "degraded",
        "service": "nenebot",
        "llm_provider": settings.llm_provider,
        "llm_model": llm_model,
        "session_backend": {
            "name": session_backend_name,
            "status": "ok" if session_backend_ok else "degraded",
            "ttl_seconds": settings.session_ttl_seconds,
        },
        "vector_store": {
            "status": "ok" if vector_index_exists and knowledge_meta_exists else "missing",
            "index_vectors": vector_store.index.ntotal,
            "index_path": settings.vector_index_path,
            "index_exists": vector_index_exists,
            "metadata_path": settings.knowledge_meta_path,
            "metadata_exists": knowledge_meta_exists,
        },
        "frontend": {
            "status": "ok" if frontend_dist_exists else "dev-mode",
            "dist_exists": frontend_dist_exists,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if session_backend_error:
        session_backend = payload["session_backend"]
        if isinstance(session_backend, dict):
            session_backend["error"] = session_backend_error

    return payload


def now_ms() -> float:
    """Return a monotonic millisecond timestamp."""
    return time.perf_counter() * 1000
