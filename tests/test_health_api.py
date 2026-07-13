import asyncio

import httpx

from src.core.config import settings
from src.main import create_app
from src.services.session_store import InMemorySessionStore


def test_public_probes_and_protected_diagnostics(monkeypatch, fake_vector_store) -> None:
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_auth_tokens", "ops-probe|ops:secret-token")
    monkeypatch.setattr(settings, "api_auth_registry_path", "/tmp/does-not-exist.json")
    fake_vector_store.add_texts(
        texts=["hello"],
        embeddings=[[1.0] + [0.0] * 511],
        metadata=[{"bot_response": "world"}],
    )

    app = create_app()
    app.state.vector_store = fake_vector_store
    app.state.session_store = InMemorySessionStore()

    async def request_endpoints() -> tuple[httpx.Response, ...]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            live = await client.get("/livez")
            ready = await client.get("/readyz")
            protected = await client.get("/ops/health")
            detailed = await client.get(
                "/ops/health",
                headers={"Authorization": "Bearer secret-token"},
            )
            return live, ready, protected, detailed

    live, ready, protected, detailed = asyncio.run(request_endpoints())

    assert live.status_code == 200
    assert ready.status_code == 200
    assert set(ready.json()) == {"status", "ready", "service", "timestamp"}
    assert protected.status_code == 401
    assert detailed.status_code == 200
    assert "vector_store" in detailed.json()
