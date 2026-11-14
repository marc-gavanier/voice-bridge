import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from voice_bridge.libraries.audio.pcm import duration
from voice_bridge.libraries.audio.tempo import stretch

RATE = 24000
TOLERANCE = 0.1


def noise(seconds: float, seed: int) -> bytes:
    return (np.random.default_rng(seed).standard_normal(round(RATE * seconds)) * 3000).astype(np.int16).tobytes()


@settings(deadline=None)
@given(
    seconds=st.floats(min_value=0.25, max_value=6.0),
    factor=st.floats(min_value=0.5, max_value=2.0),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_the_stretched_audio_lasts_its_duration_divided_by_the_pace(seconds: float, factor: float, seed: int) -> None:
    pcm = noise(seconds, seed)
    assert abs(duration(stretch(pcm, RATE, factor), RATE) - duration(pcm, RATE) / factor) <= TOLERANCE
