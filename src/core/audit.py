"""Structured audit logging helpers."""

import logging
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


def audit_log(
    event: str,
    *,
    request: Request | None = None,
    action: str,
    endpoint: str,
    **fields: Any,
) -> None:
    extra: dict[str, Any] = {
        "event": event,
        "action": action,
        "endpoint": endpoint,
    }

    if request is not None:
        auth_subject = getattr(request.state, "auth_subject", None)
        if auth_subject is not None:
            extra["auth_subject"] = auth_subject
        auth_scopes = getattr(request.state, "auth_scopes", None)
        if auth_scopes is not None:
            extra["auth_scopes"] = auth_scopes

    for key, value in fields.items():
        if value is not None:
            extra[key] = value

    logger.info(event, extra=extra)
