import asyncio

from fastapi import Response
from starlette.requests import Request

from src.core.http import RequestContextMiddleware
from src.core.observability import build_health_payload


def test_build_health_payload_reports_backend_and_vector_state(fake_vector_store) -> None:
    payload = build_health_payload(
        vector_store=fake_vector_store,
        frontend_dist_exists=False,
        session_backend_name="memory",
        session_backend_ok=True,
    )

    assert payload["status"] == "ok"
    assert payload["session_backend"]["name"] == "memory"
    assert payload["vector_store"]["index_vectors"] == 0
    assert payload["frontend"]["status"] == "dev-mode"


def test_request_context_middleware_sets_request_id_header() -> None:
    middleware = RequestContextMiddleware(app=lambda scope, receive, send: None)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/ping",
            "headers": [(b"x-request-id", b"req-123")],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "http_version": "1.1",
        }
    )

    async def call_next(_: Request) -> Response:
        return Response(content=b"ok", status_code=200)

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
