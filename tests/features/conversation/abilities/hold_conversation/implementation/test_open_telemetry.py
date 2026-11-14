from collections.abc import Iterator
from dataclasses import dataclass
from io import StringIO

import pytest
from opentelemetry.proto_json.collector.metrics.v1.metrics_service import ExportMetricsServiceRequest
from opentelemetry.proto_json.collector.trace.v1.trace_service import ExportTraceServiceRequest
from opentelemetry.proto_json.resource.v1.resource import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ExponentialHistogramDataPoint,
    HistogramDataPoint,
    InMemoryMetricReader,
    NumberDataPoint,
)
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.open_telemetry import (
    NANOSECONDS,
    OpenTelemetry,
    epoch_of,
    writing_to,
)
from voice_bridge.features.conversation.domain.turn_trace import Counted, FinishedTurn, Span

TURN = FinishedTurn(
    start=1.0,
    end=4.0,
    steps=(Span(name="transcription", start=1.0, end=1.5), Span(name="claude", start=2.0, end=3.0)),
    interrupted=True,
)


@dataclass(frozen=True)
class Exported:
    telemetry: OpenTelemetry
    spans: InMemorySpanExporter
    metrics: InMemoryMetricReader


@pytest.fixture
def exported() -> Exported:
    spans = InMemorySpanExporter()
    tracers = TracerProvider()
    tracers.add_span_processor(SimpleSpanProcessor(spans))
    metrics = InMemoryMetricReader()
    meters = MeterProvider(metric_readers=[metrics])
    telemetry = OpenTelemetry.of(
        tracers.get_tracer("test"), meters.get_meter("test"), lambda at: round(at * NANOSECONDS)
    )
    return Exported(telemetry=telemetry, spans=spans, metrics=metrics)


def finished_spans(exported: Exported) -> dict[str, ReadableSpan]:
    exported.telemetry(TURN)
    return {span.name: span for span in exported.spans.get_finished_spans()}


def points(exported: Exported, name: str) -> list[HistogramDataPoint | NumberDataPoint | ExponentialHistogramDataPoint]:
    data = exported.metrics.get_metrics_data()
    assert data is not None
    return [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]


def histogram_sums(exported: Exported, name: str) -> dict[str, float]:
    return {
        str(dict(point.attributes or {})): point.sum
        for point in points(exported, name)
        if isinstance(point, HistogramDataPoint)
    }


def counts(exported: Exported, name: str) -> dict[str, float]:
    return {
        str(dict(point.attributes or {})): point.value
        for point in points(exported, name)
        if isinstance(point, NumberDataPoint)
    }


def test_a_turn_is_one_trace_with_a_span_per_step(exported: Exported) -> None:
    assert sorted(finished_spans(exported)) == ["claude", "transcription", "turn"]


def test_a_step_belongs_to_its_turn(exported: Exported) -> None:
    spans = finished_spans(exported)
    assert spans["claude"].parent == spans["turn"].context


def test_a_step_keeps_its_own_times(exported: Exported) -> None:
    claude = finished_spans(exported)["claude"]
    assert (claude.start_time, claude.end_time) == (2 * NANOSECONDS, 3 * NANOSECONDS)


def test_a_turn_keeps_its_own_times(exported: Exported) -> None:
    turn = finished_spans(exported)["turn"]
    assert (turn.start_time, turn.end_time) == (1 * NANOSECONDS, 4 * NANOSECONDS)


def test_a_turn_tells_whether_it_was_interrupted(exported: Exported) -> None:
    assert dict(finished_spans(exported)["turn"].attributes or {}) == {"interrupted": True}


def test_each_step_lasting_is_measured(exported: Exported) -> None:
    exported.telemetry(TURN)
    assert histogram_sums(exported, "voice_bridge.step.duration") == {
        "{'step': 'transcription'}": 0.5,
        "{'step': 'claude'}": 1.0,
    }


def test_each_turn_lasting_is_measured(exported: Exported) -> None:
    exported.telemetry(TURN)
    assert histogram_sums(exported, "voice_bridge.turn.duration") == {"{'interrupted': True}": 3.0}


def test_a_counted_event_is_added_up(exported: Exported) -> None:
    exported.telemetry(Counted(name="interruption"))
    exported.telemetry(Counted(name="interruption"))
    assert counts(exported, "voice_bridge.events") == {"{'event': 'interruption'}": 2}


def test_a_stall_is_measured(exported: Exported) -> None:
    exported.telemetry.stalled(0.25)
    assert histogram_sums(exported, "voice_bridge.audio.stall.duration") == {"{}": 0.25}


def test_the_clock_is_turned_into_the_time_since_the_epoch() -> None:
    to_epoch = epoch_of(lambda: 100.0)
    assert to_epoch(101.0) - to_epoch(100.0) == NANOSECONDS


def test_the_global_providers_give_a_telemetry() -> None:
    assert isinstance(OpenTelemetry.from_globals(lambda: 0.0), OpenTelemetry)


@dataclass(frozen=True)
class Written:
    telemetry: OpenTelemetry
    tracers: TracerProvider
    meters: MeterProvider
    traces: StringIO
    metrics: StringIO


@pytest.fixture
def written() -> Iterator[Written]:
    traces, metrics = StringIO(), StringIO()
    tracers, meters = writing_to(traces, metrics, {"service.name": "voice-bridge"})
    yield Written(
        telemetry=OpenTelemetry.from_providers(tracers, meters, lambda: 0.0),
        tracers=tracers,
        meters=meters,
        traces=traces,
        metrics=metrics,
    )
    tracers.shutdown()
    meters.shutdown()


def traced_lines(written: Written) -> list[ExportTraceServiceRequest]:
    written.telemetry(TURN)
    _ = written.tracers.force_flush()
    return [ExportTraceServiceRequest.from_json(line) for line in written.traces.getvalue().splitlines()]


def measured_lines(written: Written) -> list[ExportMetricsServiceRequest]:
    written.telemetry(TURN)
    _ = written.meters.force_flush()
    return [ExportMetricsServiceRequest.from_json(line) for line in written.metrics.getvalue().splitlines()]


def span_names(line: ExportTraceServiceRequest) -> list[str | None]:
    return sorted(
        (span.name for resource in line.resource_spans for scope in resource.scope_spans for span in scope.spans),
        key=str,
    )


def metric_names(line: ExportMetricsServiceRequest) -> list[str | None]:
    return sorted(
        (
            metric.name
            for resource in line.resource_metrics
            for scope in resource.scope_metrics
            for metric in scope.metrics
        ),
        key=str,
    )


def service_of(resources: list[Resource | None]) -> list[str | None]:
    return [
        attribute.value.string_value
        for resource in resources
        if resource is not None
        for attribute in resource.attributes
        if attribute.key == "service.name" and attribute.value is not None
    ]


def test_a_turn_is_written_as_one_line_of_otlp_json(written: Written) -> None:
    assert [span_names(line) for line in traced_lines(written)] == [["claude", "transcription", "turn"]]


def test_the_written_spans_name_their_service(written: Written) -> None:
    resources = [each.resource for each in traced_lines(written)[0].resource_spans]
    assert service_of(resources) == ["voice-bridge"]


def test_the_metrics_are_written_as_otlp_json(written: Written) -> None:
    assert metric_names(measured_lines(written)[0]) == ["voice_bridge.step.duration", "voice_bridge.turn.duration"]


def test_the_written_metrics_name_their_service(written: Written) -> None:
    resources = [each.resource for each in measured_lines(written)[0].resource_metrics]
    assert service_of(resources) == ["voice-bridge"]


def traced_while_disabled(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    traces = StringIO()
    tracers, meters = writing_to(traces, StringIO(), {})
    OpenTelemetry.from_providers(tracers, meters, lambda: 0.0)(TURN)
    tracers.shutdown()
    meters.shutdown()
    return traces.getvalue()


def test_the_standard_switch_of_the_sdk_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert traced_while_disabled(monkeypatch) == ""
