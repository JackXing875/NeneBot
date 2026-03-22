import asyncio
from types import SimpleNamespace

from src.api.admin import (
    KnowledgeImportRequest,
    admin_knowledge_import,
    admin_knowledge_overview,
    admin_knowledge_rebuild,
    admin_metrics_summary,
    admin_overview,
)
from src.core.config import settings
from src.core.metrics import auth_failures_total


def test_admin_overview_returns_runtime_summary(
    fake_vector_store,
    fake_session_store,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "ops-dashboard|ops:secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")
    monkeypatch.setattr(settings, "metrics_enabled", True)
    monkeypatch.setattr(settings, "tracing_enabled", True)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=fake_vector_store,
                session_store=fake_session_store,
            )
        ),
        state=SimpleNamespace(request_id="req-admin"),
    )

    payload = asyncio.run(admin_overview(request))

    assert payload["service"]["request_id"] == "req-admin"
    assert payload["llm"]["provider"] == settings.llm_provider
    assert payload["auth"]["identities"][0]["name"] == "ops-dashboard"
    assert payload["integrations"]["metrics_enabled"] is True


def test_admin_metrics_summary_returns_preview_lines() -> None:
    auth_failures_total.inc(reason="invalid_token")

    payload = asyncio.run(admin_metrics_summary())

    assert payload["metric_series_count"] >= 1
    assert any("nenebot_auth_failures_total" in line for line in payload["preview"])


def test_admin_knowledge_overview_returns_dataset_summary(
    fake_vector_store,
    fake_session_store,
    monkeypatch,
    tmp_path,
) -> None:
    dataset_path = tmp_path / "train.jsonl"
    dataset_path.write_text(
        '{"messages":[{"role":"user","content":"你好"},{"role":"assistant","content":"你好呀"}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "data_path", str(dataset_path))

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=fake_vector_store,
                session_store=fake_session_store,
            )
        )
    )

    payload = asyncio.run(admin_knowledge_overview(request))

    assert payload["dataset"]["line_count"] == 1
    assert payload["dataset"]["preview"][0]["user"] == "你好"


def test_admin_knowledge_import_writes_dataset_without_rebuild(
    fake_vector_store,
    fake_session_store,
    monkeypatch,
    tmp_path,
) -> None:
    dataset_path = tmp_path / "train.jsonl"
    monkeypatch.setattr(settings, "data_path", str(dataset_path))

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=fake_vector_store,
                rag_pipeline=SimpleNamespace(vector_store=fake_vector_store),
                session_store=fake_session_store,
            )
        ),
        state=SimpleNamespace(auth_subject="ops-dashboard", auth_scopes=["ops"]),
    )

    payload = asyncio.run(
        admin_knowledge_import(
            KnowledgeImportRequest(
                content='{"messages":[{"role":"user","content":"测试"},{"role":"assistant","content":"导入成功"}]}',
                rebuild=False,
            ),
            request,
        )
    )

    assert payload.dataset["line_count"] == 1
    assert payload.vector_store is None
    assert dataset_path.exists()


def test_admin_knowledge_rebuild_refreshes_vector_store(
    fake_vector_store,
    fake_session_store,
    monkeypatch,
    tmp_path,
) -> None:
    dataset_path = tmp_path / "train.jsonl"
    dataset_path.write_text(
        '{"messages":[{"role":"user","content":"你好"},{"role":"assistant","content":"你好呀"}]}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "data_path", str(dataset_path))
    monkeypatch.setattr(settings, "vector_index_path", str(tmp_path / "faiss_index.bin"))
    monkeypatch.setattr(settings, "knowledge_meta_path", str(tmp_path / "knowledge_base.json"))

    def fake_rebuild() -> dict[str, object]:
        fake_vector_store.metadata = [{"query_text": "你好", "bot_response": "你好呀"}]
        return {
            "index_vectors": fake_vector_store.index.ntotal,
            "metadata_records": len(fake_vector_store.metadata),
        }

    monkeypatch.setattr("src.api.admin.rebuild_knowledge_base", fake_rebuild)
    monkeypatch.setattr(
        "src.api.admin._refresh_vector_store",
        lambda request: {
            "index_vectors": 0,
            "metadata_records": 1,
            "index_path": settings.vector_index_path,
            "metadata_path": settings.knowledge_meta_path,
        },
    )

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=fake_vector_store,
                rag_pipeline=SimpleNamespace(vector_store=fake_vector_store),
                session_store=fake_session_store,
            )
        ),
        state=SimpleNamespace(auth_subject="ops-dashboard", auth_scopes=["ops"]),
    )

    payload = asyncio.run(admin_knowledge_rebuild(request))

    assert payload.vector_store is not None
    assert payload.vector_store["metadata_records"] == 1
