import wave
from pathlib import Path

import numpy as np
import pytest

from voice_bridge.libraries.audio.file import read_audio
from voice_bridge.libraries.audio.pcm import duration, level

RATE = 48000
DAMAGED = Path(__file__).parents[2] / "fixtures" / "damaged.mp3"


def written(path: Path, rate: int, seconds: float) -> Path:
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(rate * seconds))) * 16000).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.repeat(samples, 2).tobytes())
    return path


def test_a_file_is_read_as_mono_pcm_at_the_rate_asked(tmp_path: Path) -> None:
    pcm = read_audio(written(tmp_path / "music.wav", 44100, 1.0), rate=RATE, volume=1.0)
    assert len(pcm) / 2 == pytest.approx(RATE, rel=0.01)


def test_a_file_is_read_at_the_volume_asked(tmp_path: Path) -> None:
    path = written(tmp_path / "music.wav", RATE, 0.5)
    loud, soft = level(read_audio(path, rate=RATE, volume=1.0)), level(read_audio(path, rate=RATE, volume=0.25))
    assert soft == pytest.approx(loud / 4, rel=0.01)


def test_a_damaged_frame_is_skipped_and_the_rest_of_the_file_is_read() -> None:
    assert duration(read_audio(DAMAGED, rate=RATE, volume=1.0), RATE) > 0.95
