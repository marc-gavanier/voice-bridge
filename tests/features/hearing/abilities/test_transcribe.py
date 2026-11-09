from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass

import anyio
import numpy as np
import numpy.typing as npt
import pytest

from voice_bridge.features.hearing.abilities.transcribe import Transcription, transcribe_utterances
from voice_bridge.features.hearing.domain.noise import Hallucinations

pytestmark = pytest.mark.anyio


@dataclass(frozen=True)
class Said:
    text: str
    no_speech_prob: float = 0.0
    avg_logprob: float = 0.0


@dataclass(frozen=True)
class SayingModel:
    words: str

    def transcribe(self, audio: npt.NDArray[np.float32], **options: object) -> tuple[Iterable[Said], object]:
        return iter((Said(self.words),)), (audio.size, options)


def transcription(words: str) -> Transcription:
    return Transcription(
        model=SayingModel(words),
        rate=48000,
        language="fr",
        hallucinations=Hallucinations(texts=frozenset({"merci"}), prefixes=()),
    )


async def one_utterance() -> AsyncIterator[bytes]:
    yield bytes(48000 * 2)


async def reported(words: str) -> tuple[str, bool]:
    sent, received = anyio.create_memory_object_stream[tuple[str, bool]](1)
    async with sent, received:
        await transcribe_utterances(transcription(words), one_utterance(), lambda text, noise: sent.send((text, noise)))
        return received.receive_nowait()


async def test_an_utterance_is_reported_as_its_text() -> None:
    assert await reported(" Tu en es où ?") == ("Tu en es où ?", False)


async def test_a_hallucination_is_reported_as_noise() -> None:
    assert await reported(" Merci.") == ("Merci.", True)
