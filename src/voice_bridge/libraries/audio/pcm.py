import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
import soxr

SAMPLE_BYTES: Final = 2
FULL_SCALE: Final = 32768.0
PEAK: Final = 32767.0

type Samples = npt.NDArray[np.float32]


def to_float(pcm: bytes) -> Samples:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / FULL_SCALE


def from_float(samples: Samples) -> bytes:
    return np.round(np.clip(samples, -1.0, 1.0) * PEAK).astype(np.int16).tobytes()


def level(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    return math.sqrt(np.mean(samples**2)) if samples.size else 0.0


def boost(pcm: bytes, gain: float) -> bytes:
    return from_float(np.tanh(to_float(pcm) * gain))


def scaled(pcm: bytes, volume: float) -> bytes:
    return from_float(to_float(pcm) * volume)


def ramp(pcm: bytes, start: float, end: float) -> bytes:
    samples = to_float(pcm)
    return from_float(samples * np.linspace(start, end, num=samples.size, dtype=np.float32))


def resample(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate:
        return pcm
    return from_float(soxr.resample(to_float(pcm), from_rate, to_rate))


def duration(pcm: bytes, rate: int) -> float:
    return len(pcm) / SAMPLE_BYTES / rate


@dataclass(frozen=True, slots=True, kw_only=True)
class Resampling:
    stream: soxr.ResampleStream

    def push(self, pcm: bytes) -> bytes:
        return from_float(self.stream.resample_chunk(to_float(pcm)))

    def end(self) -> bytes:
        return from_float(self.stream.resample_chunk(np.zeros(0, dtype=np.float32), last=True))


@dataclass(frozen=True, slots=True, kw_only=True)
class Unresampled:
    def push(self, pcm: bytes) -> bytes:
        return pcm

    def end(self) -> bytes:
        return b""


def resampling(from_rate: int, to_rate: int) -> Resampling | Unresampled:
    if from_rate == to_rate:
        return Unresampled()
    return Resampling(stream=soxr.ResampleStream(from_rate, to_rate, 1, dtype="float32"))
