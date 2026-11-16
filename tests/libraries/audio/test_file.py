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


def decoded(path: Path) -> bytes:
    return b"".join(decode_audio(str(path), RATE))


def test_a_file_is_decoded_as_mono_pcm_at_the_rate_asked(tmp_path: Path) -> None:
    pcm = decoded(written(tmp_path / "music.wav", 44100, 1.0))
    assert len(pcm) / 2 == pytest.approx(RATE, rel=0.01)


def test_a_file_is_decoded_frame_by_frame(tmp_path: Path) -> None:
    frames = list(decode_audio(str(written(tmp_path / "music.wav", 44100, 1.0)), RATE))
    assert len(frames) > 1


def test_a_missing_file_fails_only_when_its_first_frame_is_asked(tmp_path: Path) -> None:
    frames = decode_audio(str(tmp_path / "missing.wav"), RATE)
    with pytest.raises(FileNotFoundError):
        _ = next(frames)


def test_a_damaged_frame_is_skipped_and_the_rest_of_the_file_is_decoded() -> None:
    assert duration(decoded(DAMAGED), RATE) > 0.95


def test_a_file_that_is_not_audio_cannot_be_decoded(tmp_path: Path) -> None:
    path = tmp_path / "notes.mp3"
    _ = path.write_text("not audio", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid data"):
        _ = decoded(path)
