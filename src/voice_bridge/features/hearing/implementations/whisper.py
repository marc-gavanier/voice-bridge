from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from voice_bridge.libraries.audio.pcm import resample, to_float

if TYPE_CHECKING:
    from collections.abc import Iterable

    import numpy as np
    import numpy.typing as npt

WHISPER_RATE: Final = 16000


class Segment(Protocol):
    @property
    def text(self) -> str: ...
    @property
    def no_speech_prob(self) -> float: ...
    @property
    def avg_logprob(self) -> float: ...


class SpeechModel(Protocol):
    def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        *,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = False,
        condition_on_previous_text: bool = True,
    ) -> tuple[Iterable[Segment], object]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Transcript:
    text: str
    scores: str


def _describe(segment: Segment) -> str:
    return f"« {segment.text.strip()} » no speech {segment.no_speech_prob:.2f}, confidence {segment.avg_logprob:.2f}"


def transcribe(model: SpeechModel, pcm: bytes, rate: int, language: str) -> Transcript:
    samples = to_float(resample(pcm, from_rate=rate, to_rate=WHISPER_RATE))
    segments, _ = model.transcribe(
        samples, language=language, beam_size=1, vad_filter=True, condition_on_previous_text=False
    )
    heard = tuple(segments)
    return Transcript(
        text=" ".join(segment.text.strip() for segment in heard).strip(),
        scores=" | ".join(map(_describe, heard)) or "no segment",
    )
