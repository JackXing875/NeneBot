"""HTTP middleware and error-response helpers."""

import logging
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import NeneBotError
from src.core.request_context import get_request_id, reset_request_id, set_request_id

logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, status_code: int) -> dict[str, Any]:
    """Build the standard API error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
        },
        "request_id": get_request_id(),
    }


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request ids, emit access logs, and expose the id to clients."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)

        from src.core.observability import now_ms

        started_at = now_ms()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round(now_ms() - started_at, 2)
            logger.exception(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        else:
            duration_ms = round(now_ms() - started_at, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra={
                    "event": "request_completed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            reset_request_id(token)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTP exceptions to the standard error envelope."""
    message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("http_error", message, exc.status_code),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Normalize validation errors for API clients."""
    return JSONResponse(
        status_code=422,
        content={
            **error_payload("validation_error", "Request validation failed.", 422),
            "details": exc.errors(),
        },
    )


async def nenebot_exception_handler(request: Request, exc: NeneBotError) -> JSONResponse:
    """Preserve explicit business error codes and status codes."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.status_code),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Prevent raw tracebacks from leaking to API clients."""
    logger.exception("unhandled_exception", exc_info=exc, extra={"request_id": get_request_id()})
    return JSONResponse(
        status_code=500,
        content=error_payload("internal_error", "Internal server error.", 500),
    )
