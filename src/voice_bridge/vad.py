import numpy as np
import soxr
from faster_whisper.vad import get_vad_model

MUMBLE_RATE = 48000
VAD_RATE = 16000
WINDOW = 512
CONTEXT = 64


def load_vad_model():
    return get_vad_model()


def to_float(pcm):
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


class VoiceActivity:
    def __init__(self, model, threshold=0.5):
        self.session = model.session
        self.threshold = threshold
        self.resampler = soxr.ResampleStream(MUMBLE_RATE, VAD_RATE, 1)
        self.pending = np.zeros(0, dtype=np.float32)
        self.context = np.zeros((1, CONTEXT), dtype=np.float32)
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.probability = 0.0

    def is_voice(self, pcm):
        self.pending = np.concatenate([self.pending, self.resampler.resample_chunk(to_float(pcm))])
        while self.pending.size >= WINDOW:
            window, self.pending = self.pending[:WINDOW].reshape(1, WINDOW), self.pending[WINDOW:]
            self.probability = self._score(window)
        return self.probability >= self.threshold

    def _score(self, window):
        framed = np.concatenate([self.context, window], axis=1)
        output, self.h, self.c = self.session.run(None, {"input": framed, "h": self.h, "c": self.c})
        self.context = window[:, -CONTEXT:]
        return float(np.asarray(output).reshape(-1)[0])
