import logging
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Protocol

import anyio

from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise
from voice_bridge.features.hearing.implementations.whisper import SpeechModel, transcribe

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

logger = logging.getLogger(__name__)


class Report(Protocol):
    async def __call__(self, text: str, *, noise: bool) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcription:
    model: SpeechModel
    rate: int
    language: str
    hallucinations: Hallucinations


async def transcribe_utterances(
    transcription: Transcription,
    utterances: AsyncIterable[bytes],
    report: Report,
) -> None:
    async for pcm in utterances:
        transcript = await anyio.to_thread.run_sync(
            partial(transcribe, transcription.model, pcm, rate=transcription.rate, language=transcription.language)
        )
        logger.info("heard %r, scores: %s", transcript.text, transcript.scores)
        await report(transcript.text, noise=is_noise(transcript.text, transcription.hallucinations))
