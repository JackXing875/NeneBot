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

    assert "nenebot_http_requests_total" in rendered
    assert "nenebot_llm_requests_total" in rendered
    assert "nenebot_rag_retrieval_total" in rendered
    assert "nenebot_auth_failures_total" in rendered
    assert 'reason="invalid_token"' in rendered
    assert "nenebot_llm_retry_attempts_total" in rendered
    assert "nenebot_llm_failures_total" in rendered
