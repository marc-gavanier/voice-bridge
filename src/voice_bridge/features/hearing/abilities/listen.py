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
)
from voice_bridge.features.hearing.implementations.silero import Session, Silero, Voicing, is_voiced
from voice_bridge.features.hearing.implementations.silero import listen as score
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from voice_bridge.libraries.mumble.audio import Packet


@dataclass(frozen=True, slots=True, kw_only=True)
class Ears:
    session: Session
    voicing: Voicing
    rules: UtteranceRules
    rate: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Hearing:
    silero: Silero = field(default_factory=Silero)
    listening: Listening = field(default_factory=Listening)


@dataclass(frozen=True, slots=True, kw_only=True)
class Speaking:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Utterance:
    pcm: bytes


type Heard = Speaking | Utterance | Dismissed


def _closed(listening: Listening, now: float, rules: UtteranceRules) -> tuple[Listening, tuple[Heard, ...]]:
    remaining, closing = close(listening, now, rules)
    match closing:
        case Kept(pcm=pcm):
            return remaining, (Utterance(pcm=pcm),)
        case Dismissed():
            return remaining, (closing,)
        case None:
            return remaining, ()
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
    speaking = (Speaking(at=packet.at),) if is_speaking(listening, ears.rules) else ()
    remaining, utterance = _closed(listening, packet.at, ears.rules)
    return Hearing(silero=silero, listening=remaining), (*speaking, *utterance)


def advance(ears: Ears, state: Hearing, tick: Packet | None, now: float) -> tuple[Hearing, tuple[Heard, ...]]:
    if tick is None:
        listening, utterance = _closed(state.listening, now, ears.rules)
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
