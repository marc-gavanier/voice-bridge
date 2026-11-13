import pytest

from voice_bridge.entrypoints.telemetry import chosen_telemetry
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.open_telemetry import (
    OpenTelemetry,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import no_telemetry


def test_without_an_endpoint_nothing_is_exported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    assert chosen_telemetry(lambda: 0.0)[0] is no_telemetry


def test_with_an_endpoint_and_open_telemetry_installed_the_telemetry_is_exported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
    assert isinstance(chosen_telemetry(lambda: 0.0)[0], OpenTelemetry)
