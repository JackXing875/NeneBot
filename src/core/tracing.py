"""Lightweight tracing helpers with optional OpenTelemetry integration."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.core.config import settings
from src.core.request_context import get_request_id

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by runtime config fallback
    trace = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    OTEL_AVAILABLE = False

_TRACING_INITIALIZED = False


def tracing_available() -> bool:
    return OTEL_AVAILABLE


def setup_tracing() -> None:
    """Initialize OpenTelemetry when enabled and installed."""
    global _TRACING_INITIALIZED

    if _TRACING_INITIALIZED or not settings.tracing_enabled or not OTEL_AVAILABLE:
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.tracing_service_name})
    )

    exporter = settings.tracing_exporter.lower()
    if exporter == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACING_INITIALIZED = True


def _current_tracer():
    if not settings.tracing_enabled or not OTEL_AVAILABLE:
        return None
    setup_tracing()
    return trace.get_tracer(settings.tracing_service_name)


@contextmanager
def traced_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Create a span when tracing is enabled; otherwise act as a no-op."""
    tracer = _current_tracer()
    if tracer is None:
        yield None
        return

    merged = {"request_id": get_request_id(), **attributes}
    with tracer.start_as_current_span(name) as span:
        for key, value in merged.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def set_span_attributes(span: Any, **attributes: Any) -> None:
    if span is None:
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)
