from dataclasses import dataclass
from typing import TYPE_CHECKING

from voice_bridge.features.hearing.abilities.listen.domain.heard import Heard, Turn, heard_frame, paused
from voice_bridge.features.hearing.abilities.listen.domain.voicing import Voicing, is_voiced
from voice_bridge.features.hearing.domain.utterance import Frame, Listening, UtteranceRules
from voice_bridge.libraries.audio.pcm import duration, level

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from voice_bridge.features.hearing.abilities.listen.domain.ports import Sound, VoiceDetector


@dataclass(frozen=True, slots=True, kw_only=True)
class Ears:
    detector: VoiceDetector
    voicing: Voicing
    rules: UtteranceRules
    rate: int
    turn: Turn | None = None


def _frame(ears: Ears, sound: Sound) -> Frame:
    return Frame(
        pcm=sound.pcm,
        voiced=is_voiced(ears.voicing, probability=ears.detector(sound.pcm), volume=level(sound.pcm)),
        at=sound.at,
        duration=duration(sound.pcm, ears.rate),
    )


def advance(ears: Ears, state: Listening, tick: Sound | None, now: float) -> tuple[Listening, tuple[Heard, ...]]:
    if tick is None:
        return paused(state, now, ears.rules, ears.turn)
    return heard_frame(state, _frame(ears, tick), ears.rules, ears.turn)


async def listen(
    ears: Ears,
    ticks: AsyncIterable[Sound | None],
    report: Callable[[Heard], Awaitable[None]],
    clock: Callable[[], float],
) -> None:
    state = Listening()
    async for tick in ticks:
        state, heard = advance(ears, state, tick, clock())
        for each in heard:
            await report(each)
