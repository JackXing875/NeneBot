import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.admin import (
    admin_knowledge_import,
    admin_knowledge_overview,
    admin_knowledge_rebuild,
    admin_metrics_summary,
    admin_overview,
)
from src.core.config import settings
from src.core.metrics import auth_failures_total


def _request(fake_vector_store, fake_session_store) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=fake_vector_store,
                session_store=fake_session_store,
                character=None,
                artifact=None,
            )
        ),
        state=SimpleNamespace(request_id="req-admin"),
    )


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

    payload = asyncio.run(admin_overview(_request(fake_vector_store, fake_session_store)))

    assert payload["service"]["request_id"] == "req-admin"
    assert payload["llm"]["provider"] == settings.llm_provider
    assert payload["auth"]["identities"][0]["name"] == "ops-dashboard"
    assert payload["integrations"]["metrics_enabled"] is True
    assert payload["pack"]["status"] == "unavailable"


def test_admin_metrics_summary_returns_preview_lines() -> None:
    auth_failures_total.inc(reason="invalid_token")

    payload = asyncio.run(admin_metrics_summary())

    assert payload["metric_series_count"] >= 1
    assert any("persona_studio_auth_failures_total" in line for line in payload["preview"])


def test_admin_knowledge_overview_is_read_only(
    fake_vector_store,
    fake_session_store,
) -> None:
    payload = asyncio.run(admin_knowledge_overview(_request(fake_vector_store, fake_session_store)))

    assert payload["pack"]["status"] == "unavailable"
    assert payload["operations"]["mode"] == "offline_artifacts_only"
    assert payload["operations"]["mutable"] is False
    assert "build" in payload["operations"]["commands"]


@pytest.mark.parametrize("operation", [admin_knowledge_import, admin_knowledge_rebuild])
def test_retired_online_mutation_endpoints_return_gone(operation) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(operation())

    assert exc_info.value.status_code == 410
    assert "persona pack" in str(exc_info.value.detail)
