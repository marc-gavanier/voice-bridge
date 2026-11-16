from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pytest

from voice_bridge.features.hearing.abilities.transcribe.domain.transcript import Transcript
from voice_bridge.features.hearing.abilities.transcribe.implementation.whisper import FasterWhisper

pytestmark = pytest.mark.anyio


@dataclass(frozen=True)
class FakeSegment:
    text: str
    no_speech_prob: float
    avg_logprob: float


@dataclass(frozen=True)
class FakeModel:
    segments: tuple[FakeSegment, ...]

    def transcribe(self, audio: npt.NDArray[np.float32], **options: object) -> tuple[Iterable[FakeSegment], object]:
        return iter(self.segments), (audio.size, options)


@dataclass(frozen=True)
class LanguageEchoingModel:
    def transcribe(
        self, audio: npt.NDArray[np.float32], *, language: str | None = None, **options: object
    ) -> tuple[Iterable[FakeSegment], object]:
        return iter((FakeSegment(f"{language}", 0.0, 0.0),)), (audio.size, options)


@dataclass(frozen=True)
class SizeEchoingModel:
    def transcribe(self, audio: npt.NDArray[np.float32], **options: object) -> tuple[Iterable[FakeSegment], object]:
        return iter((FakeSegment(f"{audio.size}", 0.0, 0.0),)), options


ONE_SECOND = bytes(48000 * 2)


async def test_the_text_of_every_segment_is_joined() -> None:
    model = FakeModel(segments=(FakeSegment(" Bonjour", 0.1, -0.2), FakeSegment(" Marc. ", 0.05, -0.3)))
    transcript = await FasterWhisper(model).recognize(ONE_SECOND, rate=48000, language="fr")
    assert transcript.text == "Bonjour Marc."


async def test_the_scores_of_each_segment_are_described() -> None:
    model = FakeModel(segments=(FakeSegment(" Bonjour", 0.1, -0.2), FakeSegment(" Marc.", 0.05, -0.3)))
    transcript = await FasterWhisper(model).recognize(ONE_SECOND, rate=48000, language="fr")
    assert transcript.scores == (
        "« Bonjour » no speech 0.10, confidence -0.20 | « Marc. » no speech 0.05, confidence -0.30"
    )


async def test_no_segment_is_said_plainly() -> None:
    transcript = await FasterWhisper(FakeModel(segments=())).recognize(ONE_SECOND, rate=48000, language="fr")
    assert transcript == Transcript(text="", scores="no segment")


async def test_whisper_hears_the_language_asked() -> None:
    transcript = await FasterWhisper(LanguageEchoingModel()).recognize(ONE_SECOND, rate=48000, language="de")
    assert transcript.text == "de"


async def test_whisper_hears_the_audio_at_its_own_rate() -> None:
    transcript = await FasterWhisper(SizeEchoingModel()).recognize(ONE_SECOND, rate=48000, language="fr")
    assert transcript.text == "16000"
