from pathlib import Path
from typing import Any

import pytest

import src.runtime as runtime
from src.services.session_store import InMemorySessionStore


class UnavailableRedisSessionStore:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ConnectionError("redis unavailable")


def test_redis_failure_falls_back_to_memory_in_development(monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "app_env", "dev")
    monkeypatch.setattr(runtime.settings, "session_backend", "redis")
    monkeypatch.setattr(runtime, "RedisSessionStore", UnavailableRedisSessionStore)

    store = runtime.create_session_store()

    assert isinstance(store, InMemorySessionStore)


def test_redis_failure_is_fatal_in_production(monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "app_env", "prod")
    monkeypatch.setattr(runtime.settings, "session_backend", "redis")
    monkeypatch.setattr(runtime, "RedisSessionStore", UnavailableRedisSessionStore)

    with pytest.raises(RuntimeError, match="required Redis session backend"):
        runtime.create_session_store()


@pytest.mark.parametrize("app_env", ["staging", "prod"])
def test_missing_knowledge_artifact_is_fatal_outside_development(
    monkeypatch,
    tmp_path: Path,
    app_env: str,
) -> None:
    monkeypatch.setattr(runtime.settings, "app_env", app_env)
    monkeypatch.setattr(runtime.settings, "vector_index_path", str(tmp_path / "missing.bin"))
    monkeypatch.setattr(runtime.settings, "knowledge_meta_path", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="Build and publish it offline"):
        runtime.ensure_index_exists()


def test_existing_knowledge_artifact_is_read_only_in_production(
    monkeypatch,
    tmp_path: Path,
) -> None:
    index_path = tmp_path / "index.bin"
    metadata_path = tmp_path / "metadata.json"
    index_path.write_bytes(b"index")
    metadata_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(runtime.settings, "app_env", "prod")
    monkeypatch.setattr(runtime.settings, "vector_index_path", str(index_path))
    monkeypatch.setattr(runtime.settings, "knowledge_meta_path", str(metadata_path))

    runtime.ensure_index_exists()

    assert index_path.read_bytes() == b"index"
    assert metadata_path.read_text(encoding="utf-8") == "[]"
