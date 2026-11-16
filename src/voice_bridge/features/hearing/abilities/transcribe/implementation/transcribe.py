import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from voice_bridge.features.hearing.abilities.transcribe.domain.ports import Report, SpeechRecognizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcription:
    recognizer: SpeechRecognizer
    rate: int
    language: str
    hallucinations: Hallucinations


async def transcribe_utterances(
    transcription: Transcription,
    utterances: AsyncIterable[bytes],
    report: Report,
) -> None:
    async for pcm in utterances:
        transcript = await transcription.recognizer.recognize(
            pcm, rate=transcription.rate, language=transcription.language
        )
        logger.info("heard %r, scores: %s", transcript.text, transcript.scores)
        await report(transcript.text, noise=is_noise(transcript.text, transcription.hallucinations))
