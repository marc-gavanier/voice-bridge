import logging

import numpy as np
from faster_whisper import WhisperModel

log = logging.getLogger(__name__)


def describe_segment(segment):
    return f"« {segment.text.strip()} » sans parole {segment.no_speech_prob:.2f}, confiance {segment.avg_logprob:.2f}"


def describe_segments(segments):
    return " | ".join(map(describe_segment, segments)) or "aucun segment"


class Transcriber:
    def __init__(self, model_name, device="cuda", compute_type="int8_float16"):
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe(self, pcm_16k):
        samples = np.frombuffer(pcm_16k, dtype=np.int16).astype(np.float32) / 32768
        segments, _ = self.model.transcribe(
            samples,
            language="fr",
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        segments = list(segments)
        log.info(f"scores : {describe_segments(segments)}")
        return " ".join(segment.text.strip() for segment in segments).strip()
