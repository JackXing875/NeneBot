"""Helpers for admin-side knowledge base import and rebuild workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.infrastructure.vector_store.faiss_impl import FaissVectorStore


def _extract_dialogue_pair(item: dict[str, Any]) -> dict[str, str]:
    user_text = ""
    assistant_text = ""
    for msg in item.get("messages", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user" and not user_text:
            user_text = content
        elif role == "assistant" and not assistant_text:
            assistant_text = content
    return {"user": user_text, "assistant": assistant_text}


def summarize_dataset(file_path: str, preview_limit: int = 5) -> dict[str, Any]:
    path = Path(file_path)
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "line_count": 0,
        "preview": [],
        "last_modified": None,
    }

    if not path.exists():
        return summary

    summary["last_modified"] = datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()

    preview: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            summary["line_count"] += 1
            if len(preview) < preview_limit:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    preview.append({"user": "[invalid json]", "assistant": line[:120]})
                    continue
                if isinstance(payload, dict):
                    preview.append(_extract_dialogue_pair(payload))

    summary["preview"] = preview
    return summary


def validate_jsonl_content(content: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {idx}.") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Line {idx} must be a JSON object.")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"Line {idx} must include a non-empty messages list.")
        entries.append(payload)

    if not entries:
        raise ValueError("JSONL content is empty.")
    return entries


def write_jsonl_dataset(content: str, file_path: str) -> dict[str, Any]:
    validate_jsonl_content(content)

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return summarize_dataset(str(path))


def rebuild_knowledge_base() -> dict[str, Any]:
    from scripts.init_vector_db import main as build_index  # type: ignore[import]

    build_index()
    vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )
    return {
        "index_vectors": vector_store.index.ntotal,
        "metadata_records": len(vector_store.metadata),
        "index_path": settings.vector_index_path,
        "metadata_path": settings.knowledge_meta_path,
    }
