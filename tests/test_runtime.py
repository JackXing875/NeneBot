from pathlib import Path
from typing import Any

import pytest

import src.runtime as runtime
from src.knowledge.builder import build_pack_artifact
from src.services.session_store import InMemorySessionStore


class UnavailableRedisSessionStore:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ConnectionError("redis unavailable")


class DeterministicEncoder:
    model_name = "test/runtime-encoder"

    def encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 32
            vector[sum(text.encode("utf-8")) % len(vector)] = 1.0
            vectors.append(vector)
        return vectors


class DummyLLMClient:
    pass


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


def test_missing_active_pack_artifact_is_always_fatal(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runtime.settings, "artifact_store_path", str(tmp_path / "missing"))
    monkeypatch.setattr(runtime.settings, "active_pack_id", "mira-demo")

    with pytest.raises(RuntimeError, match="persona pack build"):
        runtime.build_runtime_services()


def test_runtime_only_reads_verified_active_artifact(monkeypatch, tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    store_path = tmp_path / "artifacts"
    encoder = DeterministicEncoder()
    published = build_pack_artifact(
        project_root / "packs" / "demo",
        store_path,
        encoder,
        activate=True,
        created_at="2026-07-14T00:00:00Z",
    )
    before = {
        path.relative_to(store_path): path.read_bytes()
        for path in store_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(runtime.settings, "artifact_store_path", str(store_path))
    monkeypatch.setattr(runtime.settings, "active_pack_id", "mira-demo")
    monkeypatch.setattr(runtime.settings, "embedding_model_name", encoder.model_name)
    monkeypatch.setattr(runtime, "EmbeddingService", lambda: encoder)
    monkeypatch.setattr(runtime, "create_llm_client", lambda: DummyLLMClient())

    services = runtime.build_runtime_services()

    after = {
        path.relative_to(store_path): path.read_bytes()
        for path in store_path.rglob("*")
        if path.is_file()
    }

    assert services.character is not None
    assert services.character.pack_id == "mira-demo"
    assert services.artifact is not None
    assert services.artifact.path == published.path
    assert services.rag_pipeline.character == services.character
    assert before == after
