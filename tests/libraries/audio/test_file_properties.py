import tempfile
import wave
from pathlib import Path

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from voice_bridge.libraries.audio.file import decode_audio
from voice_bridge.libraries.audio.pcm import duration

RATE = 48000
TOLERANCE = 0.01


def noise(path: Path, rate: int, seconds: float, seed: int) -> Path:
    samples = (np.random.default_rng(seed).standard_normal(round(rate * seconds)) * 3000).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    return path


def decoded_duration(rate: int, seconds: float, seed: int) -> float:
    with tempfile.TemporaryDirectory() as directory:
        path = noise(Path(directory) / "noise.wav", rate, seconds, seed)
        return duration(b"".join(decode_audio(str(path), RATE)), RATE)


@settings(deadline=None, max_examples=50)
@given(
    rate=st.sampled_from([8000, 16000, 22050, 24000, 44100, 48000, 96000]),
    seconds=st.floats(min_value=0.05, max_value=5.0),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_the_decoded_audio_lasts_as_long_as_the_file(rate: int, seconds: float, seed: int) -> None:
    assert abs(decoded_duration(rate, seconds, seed) - round(rate * seconds) / rate) <= TOLERANCE
