from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.hearing.abilities.listen.domain.heard import Heard, Turn, heard_frame, paused
from voice_bridge.features.hearing.abilities.listen.implementation.silero import Session, Silero, Voicing, is_voiced
from voice_bridge.features.hearing.abilities.listen.implementation.silero import listen as score
from voice_bridge.features.hearing.domain.utterance import Frame, Listening, UtteranceRules
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
    turn: Turn | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Hearing:
    silero: Silero = field(default_factory=Silero)
    listening: Listening = field(default_factory=Listening)


def _frame(ears: Ears, silero: Silero, packet: Packet) -> Frame:
    return Frame(
        pcm=packet.pcm,
        voiced=is_voiced(silero, packet.pcm, ears.voicing),
        at=packet.at,
        duration=duration(packet.pcm, ears.rate),
    )


def advance(ears: Ears, state: Hearing, tick: Packet | None, now: float) -> tuple[Hearing, tuple[Heard, ...]]:
    if tick is None:
        listening, heard = paused(state.listening, now, ears.rules, ears.turn)
        return Hearing(silero=state.silero, listening=listening), heard
    silero = score(ears.session, state.silero, tick.pcm, ears.rate)
    listening, heard = heard_frame(state.listening, _frame(ears, silero, tick), ears.rules, ears.turn)
    return Hearing(silero=silero, listening=listening), heard


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
