from collections.abc import Iterator
from dataclasses import dataclass
from io import StringIO

import pytest
from opentelemetry.proto_json.collector.logs.v1.logs_service import ExportLogsServiceRequest
from opentelemetry.proto_json.collector.metrics.v1.metrics_service import ExportMetricsServiceRequest
from opentelemetry.proto_json.collector.trace.v1.trace_service import ExportTraceServiceRequest
from opentelemetry.proto_json.resource.v1.resource import Resource
from opentelemetry.sdk._logs import LoggerProvider, ReadableLogRecord
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
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
from voice_bridge.features.conversation.domain.turn_trace import (
    Acknowledged,
    AudioStalled,
    Counted,
    FinishedTurn,
    Forwarded,
    Span,
    Understood,
)

TURN = FinishedTurn(
    start=1.0,
    end=4.0,
    steps=(Span(name="transcription", start=1.0, end=1.5), Span(name="claude", start=2.0, end=3.0)),
    interrupted=True,
)
SPOKEN = FinishedTurn(
    start=1.0,
    end=4.0,
    steps=(Span(name="synthesis", start=3.0, end=3.5, attributes=(("rank", 0), ("characters", 12))),),
    interrupted=False,
    response=2.5,
)

QUESTION = Forwarded(
    text="Où en est-on ?",
    interrupted=True,
    understood=Understood(route="question", ranking=(("question", 0.8), ("idea", 0.3))),
    acknowledgement="Voyons.",
    voice_end=1.5,
    at=2.0,
)
UNKNOWN = Forwarded(
    text="Hmm.",
    interrupted=False,
    understood=Understood(route=None, ranking=(("idea", 0.2),)),
    acknowledgement=None,
    voice_end=1.5,
    at=2.0,
)
UNROUTED_QUESTION = Forwarded(
    text="Les nouveaux seuils sont-ils activés ?",
    interrupted=False,
    understood=Understood(route=None, ranking=(("question", 0.55),), fallback="neutral_question"),
    acknowledgement="Je regarde.",
    voice_end=1.5,
    at=2.0,
)
ACKNOWLEDGED = Acknowledged(sentence="Voyons.", words="Où en est-on ?", at=2.5)


@dataclass(frozen=True)
class Exported:
    telemetry: OpenTelemetry
    spans: InMemorySpanExporter
    metrics: InMemoryMetricReader
    logs: InMemoryLogRecordExporter


@pytest.fixture
def exported() -> Exported:
    spans = InMemorySpanExporter()
    tracers = TracerProvider()
    tracers.add_span_processor(SimpleSpanProcessor(spans))
    metrics = InMemoryMetricReader()
    meters = MeterProvider(metric_readers=[metrics])
    logs = InMemoryLogRecordExporter()
    loggers = LoggerProvider(shutdown_on_exit=False)
    loggers.add_log_record_processor(SimpleLogRecordProcessor(logs))
    telemetry = OpenTelemetry.of(
        tracers.get_tracer("test"),
        meters.get_meter("test"),
        loggers.get_logger("test"),
        lambda at: round(at * NANOSECONDS),
    )
    return Exported(telemetry=telemetry, spans=spans, metrics=metrics, logs=logs)


def logged(exported: Exported, *reports: Forwarded | Acknowledged) -> list[ReadableLogRecord]:
    _ = [exported.telemetry(report) for report in reports]
    return list(exported.logs.get_finished_logs())


def event_of(exported: Exported, report: Forwarded | Acknowledged) -> tuple[str | None, int | None]:
    record = logged(exported, report)[0].log_record
    return record.event_name, record.timestamp


def attributes_of(exported: Exported, report: Forwarded | Acknowledged) -> dict[str, object]:
    return dict(logged(exported, report)[0].log_record.attributes or {})


def finished_spans(exported: Exported, turn: FinishedTurn = TURN) -> dict[str, ReadableSpan]:
    exported.telemetry(turn)
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


def test_a_step_keeps_its_attributes(exported: Exported) -> None:
    synthesis = finished_spans(exported, SPOKEN)["synthesis"]
    assert dict(synthesis.attributes or {}) == {"rank": 0, "characters": 12}


def test_a_turn_answered_tells_its_response(exported: Exported) -> None:
    assert dict(finished_spans(exported, SPOKEN)["turn"].attributes or {}) == {
        "interrupted": False,
        "response.latency": 2.5,
    }


def test_the_response_of_a_turn_answered_is_measured(exported: Exported) -> None:
    exported.telemetry(SPOKEN)
    assert histogram_sums(exported, "voice_bridge.response.latency") == {"{}": 2.5}


def test_a_turn_never_answered_measures_no_response(exported: Exported) -> None:
    exported.telemetry(TURN)
    assert histogram_sums(exported, "voice_bridge.response.latency") == {}


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
    exported.telemetry(AudioStalled(waited=0.25))
    assert histogram_sums(exported, "voice_bridge.audio.stall.duration") == {"{}": 0.25}


def test_a_forwarded_utterance_is_one_event_at_the_time_it_was_forwarded(exported: Exported) -> None:
    assert event_of(exported, QUESTION) == ("voice_bridge.utterance.forwarded", 2 * NANOSECONDS)


def test_a_forwarded_utterance_tells_what_was_said_understood_and_acknowledged(exported: Exported) -> None:
    assert attributes_of(exported, QUESTION) == {
        "voice_bridge.utterance.text": "Où en est-on ?",
        "voice_bridge.utterance.interrupted": True,
        "voice_bridge.voice.end_time_unix_nano": round(1.5 * NANOSECONDS),
        "voice_bridge.route.name": "question",
        "voice_bridge.route.ranking": ({"route": "question", "score": 0.8}, {"route": "idea", "score": 0.3}),
        "voice_bridge.acknowledgement.sentence": "Voyons.",
    }


def test_an_utterance_without_route_nor_acknowledgement_leaves_them_out(exported: Exported) -> None:
    assert attributes_of(exported, UNKNOWN) == {
        "voice_bridge.utterance.text": "Hmm.",
        "voice_bridge.utterance.interrupted": False,
        "voice_bridge.voice.end_time_unix_nano": round(1.5 * NANOSECONDS),
        "voice_bridge.route.ranking": ({"route": "idea", "score": 0.2},),
    }


def test_an_utterance_of_no_route_tells_the_pool_it_fell_back_on(exported: Exported) -> None:
    assert attributes_of(exported, UNROUTED_QUESTION)["voice_bridge.route.fallback"] == "neutral_question"


def test_an_acknowledgement_played_is_one_event_at_the_time_it_played(exported: Exported) -> None:
    assert event_of(exported, ACKNOWLEDGED) == ("voice_bridge.acknowledgement.played", round(2.5 * NANOSECONDS))


def test_an_acknowledgement_played_tells_its_sentence_and_the_words_it_answers(exported: Exported) -> None:
    assert attributes_of(exported, ACKNOWLEDGED) == {
        "voice_bridge.acknowledgement.sentence": "Voyons.",
        "voice_bridge.utterance.text": "Où en est-on ?",
    }


def test_the_events_are_logged_at_the_info_level(exported: Exported) -> None:
    assert [each.log_record.severity_text for each in logged(exported, QUESTION, ACKNOWLEDGED)] == ["INFO", "INFO"]


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
    loggers: LoggerProvider
    traces: StringIO
    metrics: StringIO
    logs: StringIO


@pytest.fixture
def written() -> Iterator[Written]:
    traces, metrics, logs = StringIO(), StringIO(), StringIO()
    tracers, meters, loggers = writing_to(
        traces, metrics, logs, {"service.name": "voice-bridge", "voice_bridge.hearing.settle": 1.5}
    )
    yield Written(
        telemetry=OpenTelemetry.from_providers(tracers, meters, loggers, lambda: 0.0),
        tracers=tracers,
        meters=meters,
        loggers=loggers,
        traces=traces,
        metrics=metrics,
        logs=logs,
    )
    tracers.shutdown()
    meters.shutdown()
    loggers.shutdown()


def traced_lines(written: Written) -> list[ExportTraceServiceRequest]:
    written.telemetry(TURN)
    _ = written.tracers.force_flush()
    return [ExportTraceServiceRequest.from_json(line) for line in written.traces.getvalue().splitlines()]


def measured_lines(written: Written) -> list[ExportMetricsServiceRequest]:
    written.telemetry(TURN)
    _ = written.meters.force_flush()
    return [ExportMetricsServiceRequest.from_json(line) for line in written.metrics.getvalue().splitlines()]


def logged_lines(written: Written) -> list[ExportLogsServiceRequest]:
    written.telemetry(QUESTION)
    _ = written.loggers.force_flush()
    return [ExportLogsServiceRequest.from_json(line) for line in written.logs.getvalue().splitlines()]


def event_names(line: ExportLogsServiceRequest) -> list[str | None]:
    return [
        record.event_name
        for resource in line.resource_logs
        for scope in resource.scope_logs
        for record in scope.log_records
    ]


def ranked_routes(line: ExportLogsServiceRequest) -> list[object]:
    return [
        attribute.value.to_dict()
        for resource in line.resource_logs
        for scope in resource.scope_logs
        for record in scope.log_records
        for attribute in record.attributes
        if attribute.key == "voice_bridge.route.ranking" and attribute.value is not None
    ]


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


def settle_of(resources: list[Resource | None]) -> list[float | None]:
    return [
        attribute.value.double_value
        for resource in resources
        if resource is not None
        for attribute in resource.attributes
        if attribute.key == "voice_bridge.hearing.settle" and attribute.value is not None
    ]


def test_a_turn_is_written_as_one_line_of_otlp_json(written: Written) -> None:
    assert [span_names(line) for line in traced_lines(written)] == [["claude", "transcription", "turn"]]


def test_the_written_spans_name_their_service(written: Written) -> None:
    resources = [each.resource for each in traced_lines(written)[0].resource_spans]
    assert service_of(resources) == ["voice-bridge"]


def test_the_written_spans_carry_the_run_configuration(written: Written) -> None:
    resources = [each.resource for each in traced_lines(written)[0].resource_spans]
    assert settle_of(resources) == [1.5]


def test_an_event_is_written_as_one_line_of_otlp_json(written: Written) -> None:
    assert [event_names(line) for line in logged_lines(written)] == [["voice_bridge.utterance.forwarded"]]


def test_the_written_events_name_their_service(written: Written) -> None:
    resources = [each.resource for each in logged_lines(written)[0].resource_logs]
    assert service_of(resources) == ["voice-bridge"]


def test_the_written_ranking_keeps_each_route_with_its_score(written: Written) -> None:
    assert ranked_routes(logged_lines(written)[0]) == [
        {
            "arrayValue": {
                "values": [
                    {
                        "kvlistValue": {
                            "values": [
                                {"key": "route", "value": {"stringValue": "question"}},
                                {"key": "score", "value": {"doubleValue": 0.8}},
                            ]
                        }
                    },
                    {
                        "kvlistValue": {
                            "values": [
                                {"key": "route", "value": {"stringValue": "idea"}},
                                {"key": "score", "value": {"doubleValue": 0.3}},
                            ]
                        }
                    },
                ]
            }
        }
    ]


def test_the_metrics_are_written_as_otlp_json(written: Written) -> None:
    assert metric_names(measured_lines(written)[0]) == ["voice_bridge.step.duration", "voice_bridge.turn.duration"]


def test_the_written_metrics_name_their_service(written: Written) -> None:
    resources = [each.resource for each in measured_lines(written)[0].resource_metrics]
    assert service_of(resources) == ["voice-bridge"]


def traced_while_disabled(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    traces, logs = StringIO(), StringIO()
    tracers, meters, loggers = writing_to(traces, StringIO(), logs, {})
    telemetry = OpenTelemetry.from_providers(tracers, meters, loggers, lambda: 0.0)
    telemetry(TURN)
    telemetry(QUESTION)
    tracers.shutdown()
    meters.shutdown()
    loggers.shutdown()
    return traces.getvalue() + logs.getvalue()


def test_the_standard_switch_of_the_sdk_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert traced_while_disabled(monkeypatch) == ""
