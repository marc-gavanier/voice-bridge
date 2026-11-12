from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from voice_bridge.features.hearing.domain.utterance import (
    Dismissed,
    Frame,
    Kept,
    Listening,
    UtteranceRules,
    close,
    hear,
    is_speaking,
    needs_turn_check,
    silent_for,
    turn_checked,
    utterance_audio,
)
from voice_bridge.features.hearing.implementations.silero import Session, Silero, Voicing, is_voiced
from voice_bridge.features.hearing.implementations.silero import listen as score
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from voice_bridge.libraries.mumble.audio import Packet


@dataclass(frozen=True, slots=True, kw_only=True)
class Turn:
    judge: Callable[[bytes], float]
    threshold: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Ears:
    session: Session
    voicing: Voicing
    rules: UtteranceRules
    rate: int
    turn: Turn | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Hearing:
    silero: Silero = field(default_factory=Silero)
    listening: Listening = field(default_factory=Listening)


@dataclass(frozen=True, slots=True, kw_only=True)
class VoiceStarted:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Speaking:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Utterance:
    pcm: bytes
    ended: float


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnChecked:
    probability: float
    pause: float
    finished: bool


type Heard = VoiceStarted | Speaking | Utterance | Dismissed | TurnChecked


def _judged(ears: Ears, listening: Listening, now: float) -> tuple[Listening, tuple[TurnChecked, ...]]:
    if ears.turn is None or not needs_turn_check(listening, now, ears.rules):
        return listening, ()
    probability = ears.turn.judge(utterance_audio(listening))
    checked = TurnChecked(
        probability=probability, pause=silent_for(listening, now), finished=probability > ears.turn.threshold
    )
    return turn_checked(listening, finished=checked.finished), (checked,)


def _closed(ears: Ears, listening: Listening, now: float) -> tuple[Listening, tuple[Heard, ...]]:
    judged, checks = _judged(ears, listening, now)
    finished = any(check.finished for check in checks)
    remaining, closing = close(judged, now, ears.rules, finished=finished)
    match closing:
        case Kept(pcm=pcm, ended=ended):
            return remaining, (*checks, Utterance(pcm=pcm, ended=ended))
        case Dismissed():
            return remaining, (*checks, closing)
        case None:
            return remaining, checks
        case _:
            assert_never(closing)


def _heard_packet(ears: Ears, state: Hearing, packet: Packet) -> tuple[Hearing, tuple[Heard, ...]]:
    silero = score(ears.session, state.silero, packet.pcm, ears.rate)
    frame = Frame(
        pcm=packet.pcm,
        voiced=is_voiced(silero, packet.pcm, ears.voicing),
        at=packet.at,
        duration=duration(packet.pcm, ears.rate),
    )
    listening = hear(state.listening, frame, ears.rules)
    started = (VoiceStarted(at=packet.at),) if listening.utterance and not state.listening.utterance else ()
    speaking = (Speaking(at=packet.at),) if is_speaking(listening, ears.rules) else ()
    remaining, utterance = _closed(ears, listening, packet.at)
    return Hearing(silero=silero, listening=remaining), (*started, *speaking, *utterance)


def advance(ears: Ears, state: Hearing, tick: Packet | None, now: float) -> tuple[Hearing, tuple[Heard, ...]]:
    if tick is None:
        listening, utterance = _closed(ears, state.listening, now)
        return Hearing(silero=state.silero, listening=listening), utterance
    return _heard_packet(ears, state, tick)


async def listen(
    ears: Ears,
    ticks: AsyncIterable[Packet | None],
    report: Callable[[Heard], Awaitable[None]],
    clock: Callable[[], float],
) -> None:
    state = Hearing()
    async for tick in ticks:
        state, heard = advance(ears, state, tick, clock())
        for each in heard:
            await report(each)
