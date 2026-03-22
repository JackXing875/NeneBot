from src.core.metrics import registry


def test_metrics_registry_renders_prometheus_text() -> None:
    rendered = registry.render()

    assert "nenebot_http_requests_total" in rendered
    assert "nenebot_llm_requests_total" in rendered
    assert "nenebot_rag_retrieval_total" in rendered
