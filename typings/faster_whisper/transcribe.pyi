from collections.abc import Iterable

import numpy as np
import numpy.typing as npt

class Segment:
    text: str
    avg_logprob: float
    no_speech_prob: float

class TranscriptionInfo:
    language: str

class WhisperModel:
    def __init__(self, model_size_or_path: str, device: str = "auto", compute_type: str = "default") -> None: ...
    def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = False,
        condition_on_previous_text: bool = True,
    ) -> tuple[Iterable[Segment], TranscriptionInfo]: ...
