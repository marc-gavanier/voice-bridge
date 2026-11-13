import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never

from opentelemetry import metrics, trace

from voice_bridge.features.conversation.domain.turn_trace import Counted, FinishedTurn

if TYPE_CHECKING:
    from collections.abc import Callable

    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Tracer

    from voice_bridge.features.conversation.domain.turn_trace import Report

NAME: Final = "voice_bridge"
NANOSECONDS: Final = 1_000_000_000


def epoch_of(clock: Callable[[], float]) -> Callable[[float], int]:
    offset = time.time_ns() - round(clock() * NANOSECONDS)

    def to_epoch(at: float) -> int:
        return round(at * NANOSECONDS) + offset

    return to_epoch


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenTelemetry:
    tracer: Tracer
    turns: Histogram
    steps: Histogram
    events: Counter
    stalls: Histogram
    to_epoch: Callable[[float], int]

    @classmethod
    def of(cls, tracer: Tracer, meter: Meter, to_epoch: Callable[[float], int]) -> OpenTelemetry:
        return cls(
            tracer=tracer,
            turns=meter.create_histogram(
                f"{NAME}.turn.duration",
                unit="s",
                description="From the end of the speaker's voice to the end of the reply",
            ),
            steps=meter.create_histogram(f"{NAME}.step.duration", unit="s", description="Each step of a turn"),
            events=meter.create_counter(f"{NAME}.events", description="Interruptions and sounds dismissed"),
            stalls=meter.create_histogram(
                f"{NAME}.audio.stall.duration", unit="s", description="Gaps in the speaker's audio reaching the bridge"
            ),
            to_epoch=to_epoch,
        )

    @classmethod
    def from_globals(cls, clock: Callable[[], float]) -> OpenTelemetry:
        return cls.of(trace.get_tracer(NAME), metrics.get_meter(NAME), epoch_of(clock))

    def _trace(self, turn: FinishedTurn) -> None:
        root = self.tracer.start_span(
            "turn", start_time=self.to_epoch(turn.start), attributes={"interrupted": turn.interrupted}
        )
        context = trace.set_span_in_context(root)
        for each in turn.steps:
            span = self.tracer.start_span(each.name, context=context, start_time=self.to_epoch(each.start))
            span.end(end_time=self.to_epoch(each.end))
            self.steps.record(each.end - each.start, {"step": each.name})
        root.end(end_time=self.to_epoch(turn.end))
        self.turns.record(turn.end - turn.start, {"interrupted": turn.interrupted})

    def __call__(self, report: Report, /) -> None:
        match report:
            case FinishedTurn():
                self._trace(report)
            case Counted(name=name):
                self.events.add(1, {"event": name})
            case _:
                assert_never(report)

    def stalled(self, seconds: float, /) -> None:
        self.stalls.record(seconds)
