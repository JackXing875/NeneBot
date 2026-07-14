from src.core.metrics import (
    auth_failures_total,
    llm_failures_total,
    llm_retry_attempts_total,
    registry,
)


def test_metrics_registry_renders_prometheus_text() -> None:
    auth_failures_total.inc(reason="invalid_token")
    llm_retry_attempts_total.inc(provider_name="deepseek", reason="timeout", attempt="1")
    llm_failures_total.inc(provider_name="deepseek", reason="timeout")
    rendered = registry.render()

    assert "persona_studio_http_requests_total" in rendered
    assert "persona_studio_llm_requests_total" in rendered
    assert "persona_studio_rag_retrieval_total" in rendered
    assert "persona_studio_auth_failures_total" in rendered
    assert 'reason="invalid_token"' in rendered
    assert "persona_studio_llm_retry_attempts_total" in rendered
    assert "persona_studio_llm_failures_total" in rendered
