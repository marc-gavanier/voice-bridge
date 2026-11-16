import wave
from pathlib import Path

import numpy as np
import pytest

from voice_bridge.libraries.audio.file import decode_audio
from voice_bridge.libraries.audio.pcm import duration

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


def test_a_file_is_decoded_as_mono_pcm_at_the_rate_asked(tmp_path: Path) -> None:
    pcm = decode_audio(written(tmp_path / "music.wav", 44100, 1.0), RATE)
    assert len(pcm) / 2 == pytest.approx(RATE, rel=0.01)


def test_a_damaged_frame_is_skipped_and_the_rest_of_the_file_is_decoded() -> None:
    assert duration(decode_audio(DAMAGED, RATE), RATE) > 0.95


def test_a_file_that_is_not_audio_cannot_be_decoded(tmp_path: Path) -> None:
    path = tmp_path / "notes.mp3"
    _ = path.write_text("not audio", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid data"):
        _ = decode_audio(path, RATE)
