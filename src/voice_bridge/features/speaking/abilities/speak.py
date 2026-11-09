import logging

from voice_bridge.features.speaking.domain.text import for_the_ear, split_sentences
from voice_bridge.features.speaking.implementations.voxtral import SynthesisError, Voxtral, synthesize

logger = logging.getLogger(__name__)


def sentences_of(text: str) -> tuple[str, ...]:
    return split_sentences(for_the_ear(text))


async def voice_of(voxtral: Voxtral, sentence: str) -> bytes | None:
    try:
        return await synthesize(voxtral, sentence)
    except SynthesisError:
        logger.warning("no voice for %r", sentence, exc_info=True)
        return None
