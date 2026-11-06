import numpy as np
from faster_whisper import WhisperModel


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
        return " ".join(segment.text.strip() for segment in segments).strip()
