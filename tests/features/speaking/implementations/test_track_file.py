import wave
from pathlib import Path

import numpy as np
import pytest

from voice_bridge.features.speaking.implementations.track_file import read_track
from voice_bridge.libraries.audio.pcm import level

RATE = 48000


def written(path: Path, rate: int, seconds: float) -> Path:
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(rate * seconds))) * 16000).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.repeat(samples, 2).tobytes())
    return path


def test_a_track_is_read_as_mono_pcm_at_the_rate_asked(tmp_path: Path) -> None:
    track = read_track(written(tmp_path / "music.wav", 44100, 1.0), rate=RATE, volume=1.0)
    assert len(track) / 2 == pytest.approx(RATE, rel=0.01)


def test_a_track_is_played_at_the_volume_asked(tmp_path: Path) -> None:
    path = written(tmp_path / "music.wav", RATE, 0.5)
    loud, soft = level(read_track(path, rate=RATE, volume=1.0)), level(read_track(path, rate=RATE, volume=0.25))
    assert soft == pytest.approx(loud / 4, rel=0.01)
