import logging
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import (
    SpeechEngine,
    SynthesisError,
    stream,
    synthesize,
)
from voice_bridge.features.speaking.domain.text import for_the_ear, split_sentences

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


def sentences_of(text: str) -> tuple[str, ...]:
    return split_sentences(for_the_ear(text))


async def voice_of(engine: SpeechEngine, sentence: str) -> bytes | None:
    try:
        return await synthesize(engine, sentence)
    except SynthesisError:
        logger.warning("no voice for %r", sentence, exc_info=True)
        return None


async def voice_streamed(engine: SpeechEngine, sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> bool:
    try:
        await stream(engine, sentence, hear)
    except SynthesisError:
        logger.warning("no voice for %r", sentence, exc_info=True)
        return False
    return True
