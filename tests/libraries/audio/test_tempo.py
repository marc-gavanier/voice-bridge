import numpy as np
import pytest

from voice_bridge.libraries.audio.pcm import duration
from voice_bridge.libraries.audio.tempo import stretch

RATE = 24000


def tone(frequency: float, seconds: float) -> bytes:
    times = np.arange(round(RATE * seconds)) / RATE
    return (np.sin(2 * np.pi * frequency * times) * 10000).astype(np.int16).tobytes()


def dominant_frequency(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    return int(np.argmax(spectrum)) * RATE / samples.size


def test_the_natural_pace_keeps_the_audio_as_it_is() -> None:
    assert stretch(tone(440, 1.0), RATE, 1.0) == tone(440, 1.0)


def test_no_audio_stays_no_audio() -> None:
    assert stretch(b"", RATE, 1.2) == b""


def test_a_faster_pace_shortens_the_audio() -> None:
    assert duration(stretch(tone(440, 1.2), RATE, 1.2), RATE) == pytest.approx(1.0, abs=0.05)


def test_a_slower_pace_lengthens_the_audio() -> None:
    assert duration(stretch(tone(440, 1.0), RATE, 0.5), RATE) == pytest.approx(2.0, abs=0.05)


def test_a_faster_pace_keeps_the_pitch() -> None:
    assert dominant_frequency(stretch(tone(440, 2.0), RATE, 1.5)) == pytest.approx(440, abs=5)
