import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never

from opentelemetry import _logs, metrics, trace
from opentelemetry._logs import SeverityNumber
from opentelemetry.exporter.otlp.json.file import FileMetricExporter, FileSpanExporter
from opentelemetry.exporter.otlp.json.file._log_exporter import FileLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from voice_bridge.features.conversation.domain.turn_trace import Acknowledged, Counted, FinishedTurn, Forwarded

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import IO

    from opentelemetry._logs import Logger
    from opentelemetry._logs import LoggerProvider as AnyLoggerProvider
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.metrics import MeterProvider as AnyMeterProvider
    from opentelemetry.trace import Tracer
    from opentelemetry.trace import TracerProvider as AnyTracerProvider
    from opentelemetry.util.types import AttributeValue

    from voice_bridge.features.conversation.domain.turn_trace import Report

NAME: Final = "voice_bridge"
NANOSECONDS: Final = 1_000_000_000


def epoch_of(clock: Callable[[], float]) -> Callable[[float], int]:
    offset = time.time_ns() - round(clock() * NANOSECONDS)

    def to_epoch(at: float) -> int:
        return round(at * NANOSECONDS) + offset

    return to_epoch


def writing_to(
    traces: IO[str], measures: IO[str], logs: IO[str], attributes: Mapping[str, AttributeValue]
) -> tuple[TracerProvider, MeterProvider, LoggerProvider]:
    resource = Resource.create(dict(attributes))
    tracers = TracerProvider(resource=resource)
    tracers.add_span_processor(BatchSpanProcessor(FileSpanExporter(stream=traces)))
    meters = MeterProvider(
        resource=resource, metric_readers=[PeriodicExportingMetricReader(FileMetricExporter(stream=measures))]
    )
    loggers = LoggerProvider(resource=resource)
    loggers.add_log_record_processor(BatchLogRecordProcessor(FileLogExporter(stream=logs)))
    return tracers, meters, loggers


def _forwarded_attributes(report: Forwarded, to_epoch: Callable[[float], int]) -> dict[str, AttributeValue]:
    understood = report.understood
    route = {} if understood.route is None else {"voice_bridge.route.name": understood.route}
    fallback = {} if understood.fallback is None else {"voice_bridge.route.fallback": understood.fallback}
    acknowledgement = (
        {} if report.acknowledgement is None else {"voice_bridge.acknowledgement.sentence": report.acknowledgement}
    )
    return {
        "voice_bridge.utterance.text": report.text,
        "voice_bridge.utterance.interrupted": report.interrupted,
        "voice_bridge.voice.end_time_unix_nano": to_epoch(report.voice_end),
        **route,
        **fallback,
        "voice_bridge.route.ranking": [{"route": name, "score": score} for name, score in understood.ranking],
        **acknowledgement,
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenTelemetry:
    tracer: Tracer
    logger: Logger
    turns: Histogram
    steps: Histogram
    responses: Histogram
    events: Counter
    stalls: Histogram
    to_epoch: Callable[[float], int]

    @classmethod
    def of(cls, tracer: Tracer, meter: Meter, logger: Logger, to_epoch: Callable[[float], int]) -> OpenTelemetry:
        return cls(
            tracer=tracer,
            logger=logger,
            turns=meter.create_histogram(
                f"{NAME}.turn.duration",
                unit="s",
                description="From the end of the speaker's voice to the end of the reply",
            ),
            steps=meter.create_histogram(f"{NAME}.step.duration", unit="s", description="Each step of a turn"),
            responses=meter.create_histogram(
                f"{NAME}.response.latency",
                unit="s",
                description="From the end of the speaker's voice to the first sound of the reply",
            ),
            events=meter.create_counter(f"{NAME}.events", description="Interruptions and sounds dismissed"),
            stalls=meter.create_histogram(
                f"{NAME}.audio.stall.duration", unit="s", description="Gaps in the speaker's audio reaching the bridge"
            ),
            to_epoch=to_epoch,
        )

    @classmethod
    def from_globals(cls, clock: Callable[[], float]) -> OpenTelemetry:
        return cls.of(trace.get_tracer(NAME), metrics.get_meter(NAME), _logs.get_logger(NAME), epoch_of(clock))

    @classmethod
    def from_providers(
        cls,
        tracers: AnyTracerProvider,
        meters: AnyMeterProvider,
        loggers: AnyLoggerProvider,
        clock: Callable[[], float],
    ) -> OpenTelemetry:
        return cls.of(tracers.get_tracer(NAME), meters.get_meter(NAME), loggers.get_logger(NAME), epoch_of(clock))

    def _event(self, name: str, at: float, attributes: Mapping[str, AttributeValue]) -> None:
        self.logger.emit(
            timestamp=self.to_epoch(at),
            severity_number=SeverityNumber.INFO,
            severity_text="INFO",
            attributes=attributes,
            event_name=name,
        )

    def _trace(self, turn: FinishedTurn) -> None:
        response = {} if turn.response is None else {"response.latency": turn.response}
        root = self.tracer.start_span(
            "turn", start_time=self.to_epoch(turn.start), attributes={"interrupted": turn.interrupted, **response}
        )
        context = trace.set_span_in_context(root)
        for each in turn.steps:
            span = self.tracer.start_span(
                each.name, context=context, start_time=self.to_epoch(each.start), attributes=dict(each.attributes)
            )
            span.end(end_time=self.to_epoch(each.end))
            self.steps.record(each.end - each.start, {"step": each.name})
        root.end(end_time=self.to_epoch(turn.end))
        self.turns.record(turn.end - turn.start, {"interrupted": turn.interrupted})
        if turn.response is not None:
            self.responses.record(turn.response)

    def __call__(self, report: Report, /) -> None:
        match report:
            case FinishedTurn():
                self._trace(report)
            case Counted(name=name):
                self.events.add(1, {"event": name})
            case Forwarded(at=at):
                self._event(f"{NAME}.utterance.forwarded", at, _forwarded_attributes(report, self.to_epoch))
            case Acknowledged(sentence=sentence, words=words, at=at):
                self._event(
                    f"{NAME}.acknowledgement.played",
                    at,
                    {"voice_bridge.acknowledgement.sentence": sentence, "voice_bridge.utterance.text": words},
                )
            case _:
                assert_never(report)

    def stalled(self, seconds: float, /) -> None:
        self.stalls.record(seconds)
