import logging
from typing import TYPE_CHECKING, Final

import stamina

from voice_bridge.features.speaking.abilities.speak.domain.ports import SynthesisError
from voice_bridge.features.speaking.domain.text import for_the_ear, split_sentences

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.speaking.abilities.speak.domain.ports import Synthesis

logger = logging.getLogger(__name__)

LONGEST_WAIT_FOR_READINESS: Final = 5.0


class NotReadyError(Exception):
    pass


def sentences_of(text: str) -> tuple[str, ...]:
    return split_sentences(for_the_ear(text))


async def voice_of(synthesis: Synthesis, sentence: str) -> bytes | None:
    try:
        return await synthesis.whole(sentence)
    except SynthesisError:
        logger.warning("no voice for %r", sentence, exc_info=True)
        return None


async def voice_streamed(synthesis: Synthesis, sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> bool:
    try:
        await synthesis.stream(sentence, hear)
    except SynthesisError:
        logger.warning("no voice for %r", sentence, exc_info=True)
        return False
    return True


async def wait_until_ready(synthesis: Synthesis) -> None:
    async for attempt in stamina.retry_context(
        on=NotReadyError, attempts=None, timeout=None, wait_max=LONGEST_WAIT_FOR_READINESS
    ):
        with attempt:
            if not await synthesis.ready():
                raise NotReadyError
