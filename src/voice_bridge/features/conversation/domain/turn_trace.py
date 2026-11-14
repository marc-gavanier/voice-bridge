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

type Attribute = str | int | float | bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Span:
    name: str
    start: float
    end: float
    attributes: tuple[tuple[str, Attribute], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Ordered:
    ticket: int
    start: float
    rank: int
    characters: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FinishedTurn:
    start: float
    end: float
    steps: tuple[Span, ...]
    interrupted: bool
    response: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Counted:
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Understood:
    route: str | None
    ranking: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Forwarded:
    text: str
    interrupted: bool
    understood: Understood
    acknowledgement: str | None
    voice_end: float
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Acknowledged:
    sentence: str
    words: str
    at: float


type Report = FinishedTurn | Counted | Forwarded | Acknowledged


@dataclass(frozen=True, slots=True, kw_only=True)
class Turn:
    start: float
    forwarded_at: float
    spoken_until: float
    steps: tuple[Span, ...]
    answered: bool = False
    synthesizing: tuple[Ordered, ...] = ()
    ordered: int = 0
    voiced: float = 0.0
    playing: tuple[Span, ...] = ()
    interrupted: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Trace:
    ending: Span | None = None
    heard_from: float | None = None
    spoken_until: float | None = None
    heard_at: float | None = None
    pieces: tuple[Span, ...] = ()
    turn: Turn | None = None


type Observed = tuple[Trace, tuple[Report, ...]]


def _finished(turn: Turn) -> FinishedTurn:
    steps = (*turn.steps, *turn.playing)
    end = max(step.end for step in steps)
    response = turn.playing[0].start - turn.spoken_until if turn.playing else None
    return FinishedTurn(start=turn.start, end=end, steps=steps, interrupted=turn.interrupted, response=response)


def forwarded(
    trace: Trace, at: float, command: Forward, understood: Understood, acknowledgement: str | None
) -> Forwarded:
    return Forwarded(
        text=command.text,
        interrupted=command.interrupted,
        understood=understood,
        acknowledgement=acknowledgement,
        voice_end=at if trace.turn is None else trace.turn.spoken_until,
        at=at,
    )


def close(trace: Trace) -> tuple[Report, ...]:
    if trace.turn is None:
        return ()
    return (_finished(trace.turn),)


def _heard_pieces(ending: Span | None, at: float) -> tuple[Span, ...]:
    if ending is None:
        return (Span(name="transcription", start=at, end=at),)
    return (ending, Span(name="transcription", start=ending.end, end=at))


def _transcribed(trace: Trace, at: float, *, noise: bool) -> Trace:
    if noise:
        return replace(trace, ending=None, heard_from=trace.heard_from if trace.pieces else None)
    pieces = (*trace.pieces, *_heard_pieces(trace.ending, at))
    spoken_until = None if trace.ending is None else trace.ending.start
    return replace(trace, ending=None, heard_at=at, spoken_until=spoken_until, pieces=pieces)


def _forwarded(trace: Trace, at: float) -> Observed:
    settle = Span(name="settle", start=at if trace.heard_at is None else trace.heard_at, end=at)
    start = at if trace.heard_from is None else trace.heard_from
    turn = Turn(
        start=start,
        forwarded_at=at,
        spoken_until=at if trace.spoken_until is None else trace.spoken_until,
        steps=(*trace.pieces, settle),
    )
    return replace(trace, heard_from=None, spoken_until=None, heard_at=None, pieces=(), turn=turn), close(trace)


def _answered(turn: Turn, at: float) -> Turn:
    if turn.answered:
        return turn
    return replace(turn, answered=True, steps=(*turn.steps, Span(name="claude", start=turn.forwarded_at, end=at)))


def _synthesized(turn: Turn, ticket: int, at: float, name: str, voiced: tuple[tuple[str, Attribute], ...] = ()) -> Turn:
    order = next((each for each in turn.synthesizing if each.ticket == ticket), None)
    if order is None:
        return turn
    rest = tuple(each for each in turn.synthesizing if each.ticket != ticket)
    attributes = (("rank", order.rank), ("characters", order.characters), *voiced)
    span = Span(name=name, start=order.start, end=at, attributes=attributes)
    return replace(turn, synthesizing=rest, steps=(*turn.steps, span))


def _played(turn: Turn, at: float) -> Turn:
    start = max((at, *(playback.end for playback in turn.playing)))
    return replace(turn, playing=(*turn.playing, Span(name="playback", start=start, end=start + turn.voiced)))


def _stopped(turn: Turn, at: float) -> Turn:
    playing = tuple(replace(each, end=min(each.end, at)) for each in turn.playing if each.start < at)
    return replace(turn, playing=playing, synthesizing=(), interrupted=True)


def _on_voice(turn: Turn, at: float, item: Synthesize | Synthesized | SynthesisFailed) -> Turn:
    match item:
        case Synthesize(ticket=ticket, sentence=sentence):
            order = Ordered(ticket=ticket, start=at, rank=turn.ordered, characters=len(sentence))
            return replace(turn, synthesizing=(*turn.synthesizing, order), ordered=turn.ordered + 1)
        case Synthesized(ticket=ticket, at=ready, duration=duration):
            synthesized = _synthesized(turn, ticket, ready, "synthesis", (("audio.duration", duration),))
            return replace(synthesized, voiced=duration)
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
                trace,
                ending=Span(name="end of turn", start=ended, end=at),
                heard_from=ended if trace.heard_from is None else trace.heard_from,
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
