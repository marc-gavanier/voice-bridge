from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voice_bridge.features.hearing.abilities.transcribe.implementation.whisper import Transcript, transcribe


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


ONE_SECOND = bytes(48000 * 2)


def test_the_text_of_every_segment_is_joined() -> None:
    model = FakeModel(segments=(FakeSegment(" Bonjour", 0.1, -0.2), FakeSegment(" Marc. ", 0.05, -0.3)))
    assert transcribe(model, ONE_SECOND, rate=48000, language="fr").text == "Bonjour Marc."


def test_the_scores_of_each_segment_are_described() -> None:
    model = FakeModel(segments=(FakeSegment(" Bonjour", 0.1, -0.2), FakeSegment(" Marc.", 0.05, -0.3)))
    assert transcribe(model, ONE_SECOND, rate=48000, language="fr").scores == (
        "« Bonjour » no speech 0.10, confidence -0.20 | « Marc. » no speech 0.05, confidence -0.30"
    )


def test_no_segment_is_said_plainly() -> None:
    assert transcribe(FakeModel(segments=()), ONE_SECOND, rate=48000, language="fr") == Transcript(
        text="", scores="no segment"
    )
