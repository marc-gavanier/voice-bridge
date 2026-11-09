import io
import wave
from typing import Final

import numpy as np

from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES, Samples, from_float, resample

UNSIGNED_8_BIT_CENTER: Final = 128.0
FULL_SCALE_BY_WIDTH: Final = {1: 128.0, 2: 32768.0, 4: 2147483648.0}
DTYPE_BY_WIDTH: Final = {1: np.uint8, 2: np.int16, 4: np.int32}


def _to_float(frames: bytes, width: int) -> Samples:
    if width not in DTYPE_BY_WIDTH:
        message = f"{width}-byte samples are not supported"
        raise ValueError(message)
    samples = np.frombuffer(frames, dtype=DTYPE_BY_WIDTH[width]).astype(np.float32)
    centered = samples - UNSIGNED_8_BIT_CENTER if width == 1 else samples
    return centered / FULL_SCALE_BY_WIDTH[width]


def decode(data: bytes, rate: int) -> bytes:
    with wave.open(io.BytesIO(data), "rb") as wav:
        source_rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
    mono = np.average(_to_float(frames, width).reshape(-1, channels), axis=1)
    return resample(from_float(mono), from_rate=source_rate, to_rate=rate)


def encode(pcm: bytes, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_BYTES)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()
