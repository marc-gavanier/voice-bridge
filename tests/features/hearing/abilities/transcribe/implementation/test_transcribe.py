from collections.abc import AsyncIterator
from dataclasses import dataclass

import anyio
import pytest
from anyio.abc import ObjectSendStream

from voice_bridge.features.hearing.abilities.transcribe.domain.ports import Report, SpeechRecognizer
from voice_bridge.features.hearing.abilities.transcribe.domain.transcript import Transcript
from voice_bridge.features.hearing.abilities.transcribe.implementation.transcribe import (
    Transcription,
    transcribe_utterances,
)
from voice_bridge.features.hearing.domain.noise import Hallucinations

pytestmark = pytest.mark.anyio


@dataclass(frozen=True)
class SayingRecognizer:
    words: str

    async def recognize(self, pcm: bytes, *, rate: int, language: str) -> Transcript:
        return Transcript(text=self.words, scores=f"{len(pcm)} bytes at {rate} Hz in {language}")


@dataclass(frozen=True)
class EchoingRecognizer:
    async def recognize(self, pcm: bytes, *, rate: int, language: str) -> Transcript:
        return Transcript(text=f"{len(pcm)} {rate} {language}", scores="")


def transcription(words: str) -> Transcription:
    return transcription_by(SayingRecognizer(words))


def transcription_by(recognizer: SpeechRecognizer) -> Transcription:
    return Transcription(
        recognizer=recognizer,
        rate=48000,
        language="fr",
        hallucinations=Hallucinations(texts=frozenset({"merci"}), prefixes=()),
    )


async def one_utterance() -> AsyncIterator[bytes]:
    yield bytes(48000 * 2)


def reporting_to(sent: ObjectSendStream[tuple[str, bool]]) -> Report:
    async def report(text: str, *, noise: bool) -> None:
        await sent.send((text, noise))

    return report


async def reported_by(transcribing: Transcription) -> tuple[str, bool]:
    sent, received = anyio.create_memory_object_stream[tuple[str, bool]](1)
    async with sent, received:
        await transcribe_utterances(transcribing, one_utterance(), reporting_to(sent))
        return received.receive_nowait()


async def reported(words: str) -> tuple[str, bool]:
    return await reported_by(transcription(words))


async def test_an_utterance_is_reported_as_its_text() -> None:
    assert await reported("Tu en es où ?") == ("Tu en es où ?", False)


async def test_a_hallucination_is_reported_as_noise() -> None:
    assert await reported("Merci.") == ("Merci.", True)


async def test_the_recognizer_hears_the_utterance_at_its_rate_in_the_language() -> None:
    assert await reported_by(transcription_by(EchoingRecognizer())) == ("96000 48000 fr", False)
