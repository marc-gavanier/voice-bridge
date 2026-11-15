from dataclasses import dataclass, field, replace
from typing import Final, assert_never

ANNOUNCED_FROM: Final = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class Recording:
    name: str
    pcm: bytes = field(repr=False)


type Said = str | Recording


@dataclass(frozen=True, slots=True, kw_only=True)
class Asked:
    sentences: tuple[Said, ...]
    ending: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Voiced:
    ticket: int
    pcm: bytes
    duration: float
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesized:
    ticket: int
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
    stop_at: float | None = None
    answered: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class SoundDismissed:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechStarted:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeechEnded:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class SilenceLasted:
    ticket: int
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class HoldLasted:
    ticket: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaudeBusy:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaudeIdle:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentsChanged:
    at_work: int


type Event = (
    Asked
    | Voiced
    | Synthesized
    | SynthesisFailed
    | VoiceDetected
    | Transcribed
    | SoundDismissed
    | SpeechStarted
    | SpeechEnded
    | SilenceLasted
    | HoldLasted
    | ClaudeBusy
    | ClaudeIdle
    | AgentsChanged
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesize:
    ticket: int
    sentence: Said


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelSynthesis:
    ticket: int


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
    pieces: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class Acknowledge:
    words: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AwaitSilence:
    ticket: int
    until: float | None = None
    lasting: float = 0.0


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Leave:
    until: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Announce:
    at_work: int


type Command = (
    Synthesize
    | CancelSynthesis
    | Play
    | StopPlaying
    | Forward
    | Acknowledge
    | AwaitSilence
    | AwaitHold
    | StartHoldMusic
    | StopHoldMusic
    | Leave
    | Announce
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthesis:
    ticket: int
    sentence: Said
    ends_at: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Scheduled:
    sentence: Said
    ends_at: float

    def plays_at(self, at: float) -> bool:
        return self.ends_at > at


@dataclass(frozen=True, slots=True, kw_only=True)
class Conversation:
    waiting: tuple[Said, ...] = ()
    synthesizing: Synthesis | None = None
    playing: tuple[Scheduled, ...] = ()
    paused: tuple[Said, ...] | None = None
    interrupted: bool = False
    hearing: bool = False
    next_ticket: int = 0
    heard: tuple[str, ...] = ()
    answered: bool = False
    settling: int | None = None
    utterances: int = 0
    reply_heard: bool = False
    voice_ended_at: float | None = None
    acknowledged: bool = False
    next_silence: int = 0
    awaiting_hold: int | None = None
    holding: bool = False
    working: bool = False
    ending: bool = False
    announcing: Announce | None = None
    settle: float = 0.0
    hold_music_delay: float = 0.0


type Step = tuple[Conversation, tuple[Command, ...]]


def unspoken(state: Conversation) -> tuple[Said, ...]:
    current = (state.synthesizing.sentence,) if state.synthesizing else ()
    return (*current, *state.waiting)


def is_talking(state: Conversation, at: float) -> bool:
    return bool(unspoken(state)) or any(scheduled.plays_at(at) for scheduled in state.playing)


def _stop_holding(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if not state.holding:
        return state, commands
    return replace(state, holding=False), (StopHoldMusic(), *commands)


def _await_hold(state: Conversation, commands: tuple[Command, ...], after: float) -> Step:
    if not state.working:
        return state, commands
    ticket = state.next_silence
    awaiting = replace(state, awaiting_hold=ticket, next_silence=ticket + 1)
    return awaiting, (*commands, AwaitHold(ticket=ticket, after=after + state.hold_music_delay))


def _await_hold_after_voice(state: Conversation, commands: tuple[Command, ...], at: float) -> Step:
    if unspoken(state):
        return state, commands
    voice_left = max((scheduled.ends_at - at for scheduled in state.playing), default=0.0)
    return _await_hold(state, commands, after=max(0.0, voice_left))


def _hold(state: Conversation, ticket: int) -> Step:
    if state.awaiting_hold != ticket:
        return state, ()
    return replace(state, awaiting_hold=None, holding=True), (StartHoldMusic(),)


def _is_quiet(state: Conversation) -> bool:
    return not (state.hearing or state.utterances or state.ending or unspoken(state))


def _announce(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if state.announcing is None or not _is_quiet(state):
        return state, commands
    announced, music = _stop_holding(replace(state, announcing=None))
    said = (*commands, *music, state.announcing)
    return _await_hold(announced, said, after=0.0) if music else (announced, said)


def _synthesize_next(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if state.hearing or state.synthesizing is not None or not state.waiting:
        return _announce(state, commands)
    synthesis = Synthesis(ticket=state.next_ticket, sentence=state.waiting[0])
    started = replace(state, waiting=state.waiting[1:], synthesizing=synthesis, next_ticket=synthesis.ticket + 1)
    return started, (*commands, Synthesize(ticket=synthesis.ticket, sentence=synthesis.sentence))


def _cancelled(state: Conversation) -> tuple[Command, ...]:
    if state.synthesizing is None:
        return ()
    return (CancelSynthesis(ticket=state.synthesizing.ticket),)


def _start_playing(state: Conversation, synthesis: Synthesis, event: Voiced) -> Step:
    if state.hearing:
        return replace(state, synthesizing=None, waiting=(synthesis.sentence, *state.waiting)), _cancelled(state)
    last_end = max((event.at, *(scheduled.ends_at for scheduled in state.playing)))
    still_playing = tuple(each for each in state.playing if each.plays_at(event.at))
    started = replace(synthesis, ends_at=last_end + event.duration)
    playing = replace(state, synthesizing=started, playing=still_playing, reply_heard=True)
    return _stop_holding(playing, (Play(pcm=event.pcm),))


def _play(state: Conversation, event: Voiced) -> Step:
    synthesis = state.synthesizing
    if synthesis is None or synthesis.ticket != event.ticket:
        return state, ()
    if synthesis.ends_at is None:
        return _start_playing(state, synthesis, event)
    longer = replace(synthesis, ends_at=max(event.at, synthesis.ends_at) + event.duration)
    return replace(state, synthesizing=longer), (Play(pcm=event.pcm),)


def _played(state: Conversation, synthesis: Synthesis) -> tuple[Scheduled, ...]:
    if synthesis.ends_at is None:
        return state.playing
    return (*state.playing, Scheduled(sentence=synthesis.sentence, ends_at=synthesis.ends_at))


def _finish(state: Conversation, event: Synthesized) -> Step:
    synthesis = state.synthesizing
    if synthesis is None or synthesis.ticket != event.ticket:
        return state, ()
    if synthesis.ends_at is None:
        return _skip(state, event.ticket)
    voiced, commands = _synthesize_next(replace(state, synthesizing=None, playing=_played(state, synthesis)))
    if unspoken(voiced):
        return voiced, commands
    if voiced.ending:
        return voiced, (*commands, Leave(until=synthesis.ends_at))
    return _await_hold(voiced, commands, after=synthesis.ends_at - event.at)


def _skip(state: Conversation, ticket: int) -> Step:
    synthesis = state.synthesizing
    if synthesis is None or synthesis.ticket != ticket:
        return state, ()
    skipped, commands = _synthesize_next(replace(state, synthesizing=None, playing=_played(state, synthesis)))
    if unspoken(skipped):
        return skipped, commands
    if skipped.ending:
        until = max((scheduled.ends_at for scheduled in skipped.playing), default=0.0)
        return skipped, (*commands, Leave(until=until))
    return _stop_holding(skipped, commands)


def _interrupt(state: Conversation, at: float) -> Step:
    if state.hearing:
        return state, ()
    if not is_talking(state, at) or not state.reply_heard:
        return _stop_holding(replace(state, hearing=True, awaiting_hold=None))
    unfinished = tuple(scheduled.sentence for scheduled in state.playing if scheduled.plays_at(at))
    stopped = (*unfinished, *unspoken(state))
    silenced = replace(state, waiting=(), synthesizing=None, playing=(), interrupted=True, hearing=True)
    return replace(silenced, paused=(*(state.paused or ()), *stopped)), (
        *_cancelled(state),
        StopPlaying(heard_at=at),
    )


def _resume(state: Conversation) -> Step:
    heard = replace(state, hearing=False)
    if heard.paused is None:
        return _synthesize_next(heard)
    resumed = replace(heard, waiting=(*heard.paused, *heard.waiting), paused=None, interrupted=False)
    return _synthesize_next(resumed)


def _settle(state: Conversation, commands: tuple[Command, ...] = ()) -> Step:
    if state.utterances > 0:
        return state, commands
    ticket = state.next_silence
    return replace(state, settling=ticket, next_silence=ticket + 1), (
        *commands,
        AwaitSilence(
            ticket=ticket,
            until=None if state.voice_ended_at is None else state.voice_ended_at + state.settle,
            lasting=state.settle,
        ),
    )


def _transcribed(state: Conversation) -> Conversation:
    return replace(state, utterances=max(0, state.utterances - 1))


def _cut(state: Conversation, at: float | None) -> Step:
    if at is None or not is_talking(state, at):
        return state, ()
    return replace(state, waiting=(), synthesizing=None, playing=(), interrupted=True), (
        *_cancelled(state),
        StopPlaying(heard_at=at),
    )


def _hear(state: Conversation, event: Transcribed) -> Step:
    cut, commands = _cut(state, event.stop_at)
    heard = replace(
        _transcribed(cut),
        heard=(*cut.heard, event.text),
        answered=event.answered,
        paused=None,
        hearing=True,
        ending=False,
    )
    return _settle(heard, commands)


def _noise(state: Conversation) -> Step:
    if not state.heard:
        return _resume(_transcribed(state))
    return _settle(_transcribed(state))


def _dismiss(state: Conversation) -> Step:
    if not state.heard:
        return _announce(_transcribed(state))
    return _settle(_transcribed(state))


def _forward(state: Conversation, ticket: int, at: float) -> Step:
    if state.settling != ticket:
        return state, ()
    acknowledging = not state.acknowledged and not is_talking(state, at)
    answered = acknowledging and state.answered and not state.interrupted and len(state.heard) == 1
    text = " ".join(state.heard)
    forward = Forward(text=text, interrupted=state.interrupted, acknowledging=acknowledging, pieces=len(state.heard))
    forwarded = replace(
        state,
        heard=(),
        settling=None,
        interrupted=False,
        hearing=False,
        reply_heard=False,
        acknowledged=state.acknowledged or acknowledging,
        working=state.working or not answered,
    )
    commands = (forward, Acknowledge(words=text)) if acknowledging else (forward,)
    return _await_hold_after_voice(*_synthesize_next(forwarded, commands), at)


def _on_claude(state: Conversation, event: Asked | Voiced | Synthesized | SynthesisFailed) -> Step:
    match event:
        case Asked(sentences=sentences, ending=ending):
            return _synthesize_next(
                replace(
                    state,
                    waiting=(*state.waiting, *sentences),
                    acknowledged=False,
                    awaiting_hold=None,
                    ending=ending,
                )
            )
        case Voiced():
            return _play(state, event)
        case Synthesized():
            return _finish(state, event)
        case SynthesisFailed(ticket=ticket):
            return _skip(state, ticket)
        case _:
            assert_never(event)


def _on_speaker(
    state: Conversation, event: VoiceDetected | Transcribed | SoundDismissed | SpeechStarted | SpeechEnded
) -> Step:
    match event:
        case VoiceDetected(at=at):
            return _interrupt(state, at)
        case Transcribed(noise=True):
            return _noise(state)
        case Transcribed():
            return _hear(state, event)
        case SoundDismissed():
            return _dismiss(state)
        case SpeechStarted():
            return replace(state, utterances=state.utterances + 1, settling=None), ()
        case SpeechEnded(at=at):
            return replace(state, voice_ended_at=at), ()
        case _:
            assert_never(event)


def _on_wait(state: Conversation, event: SilenceLasted | HoldLasted) -> Step:
    match event:
        case SilenceLasted(ticket=ticket, at=at):
            return _forward(state, ticket, at)
        case HoldLasted(ticket=ticket):
            return _hold(state, ticket)
        case _:
            assert_never(event)


def _on_activity(state: Conversation, event: ClaudeBusy | ClaudeIdle) -> Step:
    match event:
        case ClaudeBusy(at=at):
            busy = replace(state, working=True)
            return (busy, ()) if busy.hearing else _await_hold_after_voice(busy, (), at)
        case ClaudeIdle():
            return _stop_holding(replace(state, working=False, awaiting_hold=None))
        case _:
            assert_never(event)


def _on_agents(state: Conversation, event: AgentsChanged) -> Step:
    if event.at_work < ANNOUNCED_FROM:
        return replace(state, announcing=None), ()
    return _announce(replace(state, announcing=Announce(at_work=event.at_work)))


def step(state: Conversation, event: Event) -> Step:
    match event:
        case Asked() | Voiced() | Synthesized() | SynthesisFailed():
            return _on_claude(state, event)
        case VoiceDetected() | Transcribed() | SoundDismissed() | SpeechStarted() | SpeechEnded():
            return _on_speaker(state, event)
        case SilenceLasted() | HoldLasted():
            return _on_wait(state, event)
        case ClaudeBusy() | ClaudeIdle():
            return _on_activity(state, event)
        case AgentsChanged():
            return _on_agents(state, event)
        case _:
            assert_never(event)
