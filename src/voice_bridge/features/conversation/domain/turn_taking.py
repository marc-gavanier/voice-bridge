from dataclasses import dataclass, replace
from typing import assert_never


@dataclass(frozen=True, slots=True, kw_only=True)
class Asked:
    sentences: tuple[str, ...]
    working: bool = False


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


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechStarted:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SilenceLasted:
    ticket: int
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class HoldLasted:
    ticket: int


type Event = (
    Asked | Synthesized | SynthesisFailed | VoiceDetected | Transcribed | SpeechStarted | SilenceLasted | HoldLasted
)


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
    acknowledging: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Acknowledge:
    words: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AwaitSilence:
    ticket: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AwaitHold:
    ticket: int
    after: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class StartHoldMusic:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class StopHoldMusic:
    pass


type Command = (
    Synthesize | Play | StopPlaying | Forward | Acknowledge | AwaitSilence | AwaitHold | StartHoldMusic | StopHoldMusic
)


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingAcknowledgement:
    ticket: int
    words: str


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
    hearing: bool = False
    next_ticket: int = 0
    acknowledging: PendingAcknowledgement | None = None
    acknowledged: bool = False
    next_silence: int = 0
    awaiting_hold: int | None = None
    holding: bool = False
    working: bool = False


type Step = tuple[Conversation, tuple[Command, ...]]


def unspoken(state: Conversation) -> tuple[str, ...]:
    current = (state.synthesizing.sentence,) if state.synthesizing else ()
    return (*current, *state.waiting)


def is_talking(state: Conversation, at: float) -> bool:
    return bool(unspoken(state)) or any(scheduled.ends_at > at for scheduled in state.playing)


def _stop_holding(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if not state.holding:
        return state, commands
    return replace(state, holding=False), (StopHoldMusic(), *commands)


def _await_hold(state: Conversation, commands: tuple[Command, ...], after: float = 0.0) -> Step:
    if not state.working:
        return state, commands
    ticket = state.next_silence
    awaiting = replace(state, awaiting_hold=ticket, next_silence=ticket + 1)
    return awaiting, (*commands, AwaitHold(ticket=ticket, after=after))


def _hold(state: Conversation, ticket: int) -> Step:
    if state.awaiting_hold != ticket:
        return state, ()
    return replace(state, awaiting_hold=None, holding=True), (StartHoldMusic(),)


def _synthesize_next(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if state.hearing or state.synthesizing is not None or not state.waiting:
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
    voiced, commands = _synthesize_next(*_stop_holding(played, (Play(pcm=event.pcm),)))
    if unspoken(voiced):
        return voiced, commands
    return _await_hold(voiced, commands, after=scheduled.ends_at - event.at)


def _skip(state: Conversation, ticket: int) -> Step:
    if not _is_current(state, ticket):
        return state, ()
    skipped, commands = _synthesize_next(replace(state, synthesizing=None))
    if unspoken(skipped):
        return skipped, commands
    return _stop_holding(skipped, commands)


def _interrupt(state: Conversation, at: float) -> Step:
    if state.hearing:
        return state, ()
    if not is_talking(state, at):
        return _stop_holding(replace(state, hearing=True, awaiting_hold=None))
    unfinished = tuple(scheduled.sentence for scheduled in state.playing if scheduled.ends_at > at)
    stopped = (*unfinished, *unspoken(state))
    silenced = replace(state, waiting=(), synthesizing=None, playing=(), interrupted=True, hearing=True)
    return replace(silenced, paused=(*(state.paused or ()), *stopped)), (StopPlaying(heard_at=at),)


def _resume(state: Conversation) -> Step:
    heard = replace(state, hearing=False)
    if heard.paused is None:
        return _synthesize_next(heard)
    resumed = replace(heard, waiting=(*heard.paused, *heard.waiting), paused=None, interrupted=False)
    return _synthesize_next(resumed)


def _forward(state: Conversation, text: str) -> Step:
    if state.acknowledged:
        forwarded = replace(state, paused=None, interrupted=False, hearing=False, acknowledging=None)
        return _synthesize_next(
            *_await_hold(forwarded, (Forward(text=text, interrupted=state.interrupted, acknowledging=False),))
        )
    pending = PendingAcknowledgement(ticket=state.next_silence, words=text)
    forwarded = replace(
        state, paused=None, interrupted=False, hearing=False, acknowledging=pending, next_silence=pending.ticket + 1
    )
    awaited = AwaitSilence(ticket=pending.ticket)
    return _synthesize_next(forwarded, (awaited, Forward(text=text, interrupted=state.interrupted, acknowledging=True)))


def _acknowledge(state: Conversation, ticket: int, at: float) -> Step:
    pending = state.acknowledging
    if pending is None or pending.ticket != ticket:
        return state, ()
    if is_talking(state, at):
        return replace(state, acknowledging=None), ()
    acknowledged = replace(state, acknowledging=None, acknowledged=True)
    return _await_hold(acknowledged, (Acknowledge(words=pending.words),))


def _on_claude(state: Conversation, event: Asked | Synthesized | SynthesisFailed) -> Step:
    match event:
        case Asked(sentences=sentences, working=working):
            return _synthesize_next(
                replace(
                    state,
                    waiting=(*state.waiting, *sentences),
                    acknowledging=None,
                    acknowledged=False,
                    awaiting_hold=None,
                    working=working,
                )
            )
        case Synthesized():
            return _play(state, event)
        case SynthesisFailed(ticket=ticket):
            return _skip(state, ticket)
        case _:
            assert_never(event)


def _on_speaker(
    state: Conversation, event: VoiceDetected | Transcribed | SpeechStarted | SilenceLasted | HoldLasted
) -> Step:
    match event:
        case VoiceDetected(at=at):
            return _interrupt(state, at)
        case Transcribed(noise=True):
            return _resume(state)
        case Transcribed(text=text):
            return _forward(state, text)
        case SpeechStarted():
            return replace(state, acknowledging=None), ()
        case SilenceLasted(ticket=ticket, at=at):
            return _acknowledge(state, ticket, at)
        case HoldLasted(ticket=ticket):
            return _hold(state, ticket)
        case _:
            assert_never(event)


def step(state: Conversation, event: Event) -> Step:
    match event:
        case Asked() | Synthesized() | SynthesisFailed():
            return _on_claude(state, event)
        case VoiceDetected() | Transcribed() | SpeechStarted() | SilenceLasted() | HoldLasted():
            return _on_speaker(state, event)
        case _:
            assert_never(event)
