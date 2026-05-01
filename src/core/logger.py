"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys

from src.core.config import settings
from src.core.observability import JsonFormatter


def setup_logger() -> logging.Logger:
    """Initializes the global logger with standard industrial formatting."""
    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("NeneBot")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root.setLevel(settings.log_level)
    root.handlers = [handler]
    return logging.getLogger("NeneBot")
