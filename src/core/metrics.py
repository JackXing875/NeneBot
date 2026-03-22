"""Prometheus-compatible in-process metrics registry."""

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import DefaultDict


def _normalize_labels(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _render_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    rendered = ",".join(f'{key}="{value}"' for key, value in labels)
    return f"{{{rendered}}}"


@dataclass
class CounterMetric:
    """Monotonic counter metric."""

    name: str
    help_text: str
    values: DefaultDict[tuple[tuple[str, str], ...], float] = field(
        default_factory=lambda: defaultdict(float)
    )

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        self.values[_normalize_labels(labels)] += amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        for labels, value in sorted(self.values.items()):
            lines.append(f"{self.name}{_render_labels(labels)} {value}")
        return lines


@dataclass
class HistogramMetric:
    """Minimal histogram metric with cumulative bucket rendering."""

    name: str
    help_text: str
    buckets: tuple[float, ...]
    bucket_values: DefaultDict[tuple[tuple[str, str], ...], dict[float, float]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    sums: DefaultDict[tuple[tuple[str, str], ...], float] = field(
        default_factory=lambda: defaultdict(float)
    )
    counts: DefaultDict[tuple[tuple[str, str], ...], float] = field(
        default_factory=lambda: defaultdict(float)
    )

    def observe(self, value: float, **labels: str) -> None:
        normalized = _normalize_labels(labels)
        current = self.bucket_values[normalized]
        for bucket in self.buckets:
            current[bucket] = current.get(bucket, 0.0) + (1.0 if value <= bucket else 0.0)
        current[float("inf")] = current.get(float("inf"), 0.0) + 1.0
        self.sums[normalized] += value
        self.counts[normalized] += 1.0

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} histogram"]
        for labels, bucket_map in sorted(self.bucket_values.items()):
            for bucket in (*self.buckets, float("inf")):
                bucket_labels = dict(labels)
                bucket_labels["le"] = "+Inf" if bucket == float("inf") else str(bucket)
                lines.append(
                    f"{self.name}_bucket{_render_labels(_normalize_labels(bucket_labels))} "
                    f"{bucket_map.get(bucket, 0.0)}"
                )
            lines.append(f"{self.name}_sum{_render_labels(labels)} {self.sums[labels]}")
            lines.append(f"{self.name}_count{_render_labels(labels)} {self.counts[labels]}")
        return lines


class MetricsRegistry:
    """Thread-safe registry for counters and histograms."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, CounterMetric] = {}
        self._histograms: dict[str, HistogramMetric] = {}

    def counter(self, name: str, help_text: str) -> CounterMetric:
        with self._lock:
            metric = self._counters.get(name)
            if metric is None:
                metric = CounterMetric(name=name, help_text=help_text)
                self._counters[name] = metric
            return metric

    def histogram(self, name: str, help_text: str, buckets: tuple[float, ...]) -> HistogramMetric:
        with self._lock:
            metric = self._histograms.get(name)
            if metric is None:
                metric = HistogramMetric(name=name, help_text=help_text, buckets=buckets)
                self._histograms[name] = metric
            return metric

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for metric in self._counters.values():
                lines.extend(metric.render())
            for metric in self._histograms.values():
                lines.extend(metric.render())
        return "\n".join(lines) + "\n"


registry = MetricsRegistry()
http_requests_total = registry.counter(
    "nenebot_http_requests_total",
    "Total HTTP requests processed by NeneBot.",
)
http_request_duration_ms = registry.histogram(
    "nenebot_http_request_duration_ms",
    "HTTP request latency in milliseconds.",
    buckets=(10, 50, 100, 250, 500, 1000, 3000, 10000),
)
rag_retrieval_total = registry.counter(
    "nenebot_rag_retrieval_total",
    "Total RAG retrieval operations.",
)
rag_retrieval_duration_ms = registry.histogram(
    "nenebot_rag_retrieval_duration_ms",
    "RAG retrieval latency in milliseconds.",
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000),
)
llm_requests_total = registry.counter(
    "nenebot_llm_requests_total",
    "Total LLM request attempts by provider and mode.",
)
llm_request_duration_ms = registry.histogram(
    "nenebot_llm_request_duration_ms",
    "LLM request latency in milliseconds.",
    buckets=(50, 100, 250, 500, 1000, 3000, 10000, 30000),
)
rate_limit_exceeded_total = registry.counter(
    "nenebot_rate_limit_exceeded_total",
    "Total requests rejected by the in-memory rate limiter.",
)
auth_failures_total = registry.counter(
    "nenebot_auth_failures_total",
    "Total authentication failures grouped by reason.",
)
llm_retry_attempts_total = registry.counter(
    "nenebot_llm_retry_attempts_total",
    "Total LLM retry attempts grouped by provider and failure type.",
)
llm_failures_total = registry.counter(
    "nenebot_llm_failures_total",
    "Total LLM failures grouped by provider and terminal error type.",
)
