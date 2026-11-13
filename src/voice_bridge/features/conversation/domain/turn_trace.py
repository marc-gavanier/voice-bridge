from dataclasses import dataclass, replace
from typing import assert_never

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Event,
    Forward,
    Play,
    SoundDismissed,
    SpeechEnded,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Span:
    name: str
    start: float
    end: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FinishedTurn:
    start: float
    end: float
    steps: tuple[Span, ...]
    interrupted: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Counted:
    name: str


type Report = FinishedTurn | Counted


@dataclass(frozen=True, slots=True, kw_only=True)
class Turn:
    start: float
    forwarded_at: float
    steps: tuple[Span, ...]
    answered: bool = False
    synthesizing: tuple[tuple[int, float], ...] = ()
    voiced: float = 0.0
    playing: tuple[Span, ...] = ()
    interrupted: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Trace:
    voice_ended_at: float | None = None
    heard_from: float | None = None
    heard_at: float | None = None
    pieces: tuple[Span, ...] = ()
    turn: Turn | None = None


type Observed = tuple[Trace, tuple[Report, ...]]


def _finished(turn: Turn) -> FinishedTurn:
    steps = (*turn.steps, *turn.playing)
    end = max(step.end for step in steps)
    return FinishedTurn(start=turn.start, end=end, steps=steps, interrupted=turn.interrupted)


def close(trace: Trace) -> tuple[Report, ...]:
    if trace.turn is None:
        return ()
    return (_finished(trace.turn),)


def _transcribed(trace: Trace, at: float, *, noise: bool) -> Trace:
    if noise:
        return replace(trace, voice_ended_at=None, heard_from=trace.heard_from if trace.pieces else None)
    piece = Span(name="transcription", start=at if trace.voice_ended_at is None else trace.voice_ended_at, end=at)
    return replace(trace, voice_ended_at=None, heard_at=at, pieces=(*trace.pieces, piece))


def _forwarded(trace: Trace, at: float) -> Observed:
    settle = Span(name="settle", start=at if trace.heard_at is None else trace.heard_at, end=at)
    turn = Turn(
        start=at if trace.heard_from is None else trace.heard_from,
        forwarded_at=at,
        steps=(*trace.pieces, settle),
    )
    return replace(trace, heard_from=None, heard_at=None, pieces=(), turn=turn), close(trace)


def _answered(turn: Turn, at: float) -> Turn:
    if turn.answered:
        return turn
    return replace(turn, answered=True, steps=(*turn.steps, Span(name="claude", start=turn.forwarded_at, end=at)))


def _synthesized(turn: Turn, ticket: int, at: float, name: str) -> Turn:
    started = dict(turn.synthesizing)
    if ticket not in started:
        return turn
    rest = tuple((each, start) for each, start in turn.synthesizing if each != ticket)
    return replace(turn, synthesizing=rest, steps=(*turn.steps, Span(name=name, start=started[ticket], end=at)))


def _played(turn: Turn, at: float) -> Turn:
    start = max((at, *(playback.end for playback in turn.playing)))
    return replace(turn, playing=(*turn.playing, Span(name="playback", start=start, end=start + turn.voiced)))


def _stopped(turn: Turn, at: float) -> Turn:
    playing = tuple(replace(each, end=min(each.end, at)) for each in turn.playing if each.start < at)
    return replace(turn, playing=playing, synthesizing=(), interrupted=True)


def _on_voice(turn: Turn, at: float, item: Synthesize | Synthesized | SynthesisFailed) -> Turn:
    match item:
        case Synthesize(ticket=ticket):
            return replace(turn, synthesizing=(*turn.synthesizing, (ticket, at)))
        case Synthesized(ticket=ticket, at=ready, duration=duration):
            return replace(_synthesized(turn, ticket, ready, "synthesis"), voiced=duration)
        case SynthesisFailed(ticket=ticket):
            return _synthesized(turn, ticket, at, "failed synthesis")
        case _:
            assert_never(item)


def _on_turn(turn: Turn, at: float, item: Event | Command) -> Turn:
    match item:
        case Asked():
            return _answered(turn, at)
        case Synthesize() | Synthesized() | SynthesisFailed():
            return _on_voice(turn, at, item)
        case Play():
            return _played(turn, at)
        case StopPlaying(heard_at=heard_at):
            return _stopped(turn, heard_at)
        case _:
            return turn


def _counted(item: Event | Command) -> tuple[Report, ...]:
    match item:
        case SoundDismissed():
            return (Counted(name="sound dismissed"),)
        case StopPlaying():
            return (Counted(name="interruption"),)
        case _:
            return ()


def _on_speech(trace: Trace, at: float, item: Event | Command) -> Trace:
    match item:
        case SpeechEnded(at=ended):
            return replace(
                trace, voice_ended_at=ended, heard_from=ended if trace.heard_from is None else trace.heard_from
            )
        case Transcribed(noise=noise):
            return _transcribed(trace, at, noise=noise)
        case SoundDismissed():
            return replace(trace, heard_from=trace.heard_from if trace.pieces else None)
        case _:
            return trace


def observe(trace: Trace, at: float, item: Event | Command) -> Observed:
    if isinstance(item, Forward):
        return _forwarded(trace, at)
    spoken = _on_speech(trace, at, item)
    turn = None if spoken.turn is None else _on_turn(spoken.turn, at, item)
    return replace(spoken, turn=turn), _counted(item)
