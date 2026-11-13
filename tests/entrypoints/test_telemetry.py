import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, override

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from voice_bridge.entrypoints.telemetry import chosen_telemetry, report_errors
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.open_telemetry import (
    OpenTelemetry,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import no_telemetry

if TYPE_CHECKING:
    from sentry_sdk._types import Event


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


class CapturedTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Envelope] = []

    @override
    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)


@pytest.fixture
def sentry(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> Iterator[CapturedTransport]:
    monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.example.org/1")
    caplog.set_level(logging.INFO)
    transport = CapturedTransport()
    _ = report_errors(transport)
    yield transport
    sentry_sdk.get_client().close()
    _ = sentry_sdk.init()


def events_of(transport: CapturedTransport) -> list[Event]:
    sentry_sdk.flush()
    return [event for envelope in transport.envelopes if (event := envelope.get_event()) is not None]


def broken(said: str) -> None:
    raise ValueError(len(said))


def log_entries(transport: CapturedTransport) -> list[object]:
    return [event.get("logentry") for event in events_of(transport)]


def failed_with(said: str) -> None:
    logger = logging.getLogger("voice_bridge.test")
    logger.info("heard %r", said)
    try:
        broken(said)
    except ValueError:
        logger.exception("stopped on an unexpected error")


def test_without_a_sentry_dsn_no_error_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert not report_errors()


def test_an_error_logged_reaches_sentry(sentry: CapturedTransport) -> None:
    failed_with("what the speaker said")
    assert log_entries(sentry) == [
        {"message": "stopped on an unexpected error", "params": [], "formatted": "stopped on an unexpected error"}
    ]


def test_the_lines_logged_before_an_error_do_not_reach_sentry(sentry: CapturedTransport) -> None:
    failed_with("what the speaker said")
    assert "what the speaker said" not in repr(events_of(sentry))
