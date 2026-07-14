import asyncio

from fastapi import HTTPException
from starlette.requests import Request

from src.core.exceptions import PersonaStudioError
from src.core.http import (
    application_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from src.core.request_context import reset_request_id, set_request_id


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "http_version": "1.1",
        }
    )


def test_http_exception_uses_standard_error_envelope() -> None:
    token = set_request_id("req-http")
    response = asyncio.run(
        http_exception_handler(make_request(), HTTPException(status_code=404, detail="missing"))
    )
    reset_request_id(token)
    payload = response.body.decode()
    assert response.status_code == 404
    assert '"code":"http_error"' in payload
    assert '"message":"missing"' in payload
    assert '"request_id":"req-http"' in payload


def test_unhandled_exception_uses_internal_error_envelope() -> None:
    token = set_request_id("req-internal")
    response = asyncio.run(unhandled_exception_handler(make_request(), RuntimeError("boom")))
    reset_request_id(token)
    payload = response.body.decode()
    assert response.status_code == 500
    assert '"code":"internal_error"' in payload
    assert '"request_id":"req-internal"' in payload


def test_application_exception_preserves_business_code() -> None:
    token = set_request_id("req-biz")
    response = asyncio.run(
        application_exception_handler(
            make_request(),
            PersonaStudioError(
                "provider unavailable",
                code="llm_unavailable",
                status_code=503,
            ),
        )
    )
    reset_request_id(token)
    payload = response.body.decode()
    assert response.status_code == 503
    assert '"code":"llm_unavailable"' in payload
    assert '"message":"provider unavailable"' in payload
