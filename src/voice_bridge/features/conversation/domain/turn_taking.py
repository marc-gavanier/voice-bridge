from dataclasses import dataclass, replace
from typing import assert_never


@dataclass(frozen=True, slots=True, kw_only=True)
class Asked:
    sentences: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesized:
    ticket: int
    pcm: bytes
    duration: float
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SynthesisFailed:
    ticket: int


@dataclass(frozen=True, slots=True, kw_only=True)
class VoiceDetected:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcribed:
    text: str
    noise: bool = False


type Event = Asked | Synthesized | SynthesisFailed | VoiceDetected | Transcribed


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesize:
    ticket: int
    sentence: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Play:
    pcm: bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class StopPlaying:
    heard_at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Forward:
    text: str
    interrupted: bool


type Command = Synthesize | Play | StopPlaying | Forward


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesis:
    ticket: int
    sentence: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Scheduled:
    sentence: str
    ends_at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Conversation:
    waiting: tuple[str, ...] = ()
    synthesizing: Synthesis | None = None
    playing: tuple[Scheduled, ...] = ()
    paused: tuple[str, ...] | None = None
    interrupted: bool = False
    next_ticket: int = 0


type Step = tuple[Conversation, tuple[Command, ...]]


def unspoken(state: Conversation) -> tuple[str, ...]:
    current = (state.synthesizing.sentence,) if state.synthesizing else ()
    return (*current, *state.waiting)


def is_talking(state: Conversation, at: float) -> bool:
    return bool(unspoken(state)) or any(scheduled.ends_at > at for scheduled in state.playing)


def _synthesize_next(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if state.synthesizing is not None or not state.waiting:
        return state, commands
    synthesis = Synthesis(ticket=state.next_ticket, sentence=state.waiting[0])
    started = replace(state, waiting=state.waiting[1:], synthesizing=synthesis, next_ticket=synthesis.ticket + 1)
    return started, (*commands, Synthesize(ticket=synthesis.ticket, sentence=synthesis.sentence))


def _is_current(state: Conversation, ticket: int) -> bool:
    return state.synthesizing is not None and state.synthesizing.ticket == ticket


def _play(state: Conversation, event: Synthesized) -> Step:
    if state.synthesizing is None or not _is_current(state, event.ticket):
        return state, ()
    last_end = max((scheduled.ends_at for scheduled in state.playing if scheduled.ends_at > event.at), default=event.at)
    scheduled = Scheduled(sentence=state.synthesizing.sentence, ends_at=last_end + event.duration)
    still_playing = tuple(each for each in state.playing if each.ends_at > event.at)
    played = replace(state, synthesizing=None, playing=(*still_playing, scheduled))
    return _synthesize_next(played, (Play(pcm=event.pcm),))


def _skip(state: Conversation, ticket: int) -> Step:
    if not _is_current(state, ticket):
        return state, ()
    return _synthesize_next(replace(state, synthesizing=None))


def _interrupt(state: Conversation, at: float) -> Step:
    if not is_talking(state, at):
        return state, ()
    unfinished = tuple(scheduled.sentence for scheduled in state.playing if scheduled.ends_at > at)
    stopped = (*unfinished, *unspoken(state))
    silenced = replace(state, waiting=(), synthesizing=None, playing=(), interrupted=True)
    return replace(silenced, paused=(*(state.paused or ()), *stopped)), (StopPlaying(heard_at=at),)


def _resume(state: Conversation) -> Step:
    if state.paused is None:
        return state, ()
    resumed = replace(state, waiting=(*state.waiting, *state.paused), paused=None, interrupted=False)
    return _synthesize_next(resumed)


def _forward(state: Conversation, text: str) -> Step:
    forwarded = replace(state, paused=None, interrupted=False)
    return forwarded, (Forward(text=text, interrupted=state.interrupted),)


def step(state: Conversation, event: Event) -> Step:
    match event:
        case Asked(sentences=sentences):
            return _synthesize_next(replace(state, waiting=(*state.waiting, *sentences)))
        case Synthesized():
            return _play(state, event)
        case SynthesisFailed(ticket=ticket):
            return _skip(state, ticket)
        case VoiceDetected(at=at):
            return _interrupt(state, at)
        case Transcribed(noise=True):
            return _resume(state)
        case Transcribed(text=text):
            return _forward(state, text)
        case _:
            assert_never(event)
