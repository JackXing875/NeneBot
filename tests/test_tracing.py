from src.core.tracing import set_span_attributes, traced_span, tracing_available


class FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


def test_set_span_attributes_is_noop_for_none() -> None:
    set_span_attributes(None, foo="bar")


def test_set_span_attributes_updates_span() -> None:
    span = FakeSpan()

    set_span_attributes(span, foo="bar", count=1)

    assert span.attributes["foo"] == "bar"
    assert span.attributes["count"] == 1


def test_traced_span_is_usable_without_enabled_tracing() -> None:
    with traced_span("test.span") as span:
        assert span is None or tracing_available()
