import json
import logging

from starlette.requests import Request

from src.core.audit import audit_log
from src.core.observability import JsonFormatter


def make_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
        "http_version": "1.1",
        "state": {},
    }
    request = Request(scope)
    request.state.auth_subject = "ci-bot"
    request.state.auth_scopes = ["chat"]
    return request


def test_audit_log_emits_structured_fields() -> None:
    request = make_request()
    logger = logging.getLogger("src.core.audit")
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(JsonFormatter().format(record))

    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        audit_log(
            "audit_chat_requested",
            request=request,
            action="chat_completion",
            endpoint="/v1/chat",
            session_id="sess-1",
            query_length=12,
        )
    finally:
        logger.removeHandler(handler)

    payload = json.loads(records[0])
    assert payload["event"] == "audit_chat_requested"
    assert payload["action"] == "chat_completion"
    assert payload["endpoint"] == "/v1/chat"
    assert payload["auth_subject"] == "ci-bot"
    assert payload["auth_scopes"] == ["chat"]
    assert payload["session_id"] == "sess-1"
