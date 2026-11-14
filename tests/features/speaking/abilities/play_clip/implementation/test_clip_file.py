import wave
from pathlib import Path

import numpy as np
import pytest

from voice_bridge.features.speaking.abilities.play_clip.implementation.clip_file import (
    ClipRefusedError,
    ClipRules,
    read_clip,
)
from voice_bridge.libraries.audio.pcm import level

RATE = 48000
LARGEST = 1_000_000
LONGEST = 2.0


def rules(directory: Path, *, volume: float = 1.0) -> ClipRules:
    return ClipRules(directory=directory, largest=LARGEST, longest=LONGEST, volume=volume)


def written(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(RATE * seconds))) * 16000).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(samples.tobytes())
    return path


def clips(tmp_path: Path) -> Path:
    return tmp_path / "clips"


def refusal(path: Path | str, directory: Path) -> str:
    with pytest.raises(ClipRefusedError) as refused:
        _ = read_clip(str(path), rules=rules(directory), rate=RATE)
    return str(refused.value)


def test_a_clip_in_the_directory_is_read_as_pcm_at_the_rate_asked(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.wav", 1.0)
    assert len(read_clip(str(clip), rules=rules(clips(tmp_path)), rate=RATE)) == RATE * 2


def test_a_clip_in_a_folder_of_the_directory_is_read(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "comparison" / "sample.wav", 1.0)
    assert len(read_clip(str(clip), rules=rules(clips(tmp_path)), rate=RATE)) == RATE * 2


def test_a_clip_is_read_at_the_volume_set(tmp_path: Path) -> None:
    clip = str(written(clips(tmp_path) / "sample.wav", 0.5))
    loud = level(read_clip(clip, rules=rules(clips(tmp_path)), rate=RATE))
    soft = level(read_clip(clip, rules=rules(clips(tmp_path), volume=0.25), rate=RATE))
    assert soft == pytest.approx(loud / 4, rel=0.01)


def test_a_clip_with_an_upper_case_suffix_is_read(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "SAMPLE.WAV", 1.0)
    assert len(read_clip(str(clip), rules=rules(clips(tmp_path)), rate=RATE)) == RATE * 2


def test_a_relative_path_is_refused(tmp_path: Path) -> None:
    _ = written(clips(tmp_path) / "sample.wav", 1.0)
    assert refusal("sample.wav", clips(tmp_path)) == "sample.wav is not an absolute path"


def test_a_file_outside_the_directory_is_refused(tmp_path: Path) -> None:
    clip = written(tmp_path / "elsewhere" / "sample.wav", 1.0)
    assert refusal(clip, clips(tmp_path)) == f"{clip} is outside {clips(tmp_path)}, where clips must be"


def test_a_path_climbing_out_of_the_directory_is_refused(tmp_path: Path) -> None:
    _ = written(tmp_path / "sample.wav", 1.0)
    climbing = clips(tmp_path) / ".." / "sample.wav"
    clips(tmp_path).mkdir()
    assert refusal(climbing, clips(tmp_path)) == f"{climbing} is outside {clips(tmp_path)}, where clips must be"


def test_a_link_in_the_directory_to_a_file_outside_is_refused(tmp_path: Path) -> None:
    outside = written(tmp_path / "sample.wav", 1.0)
    link = clips(tmp_path) / "link.wav"
    clips(tmp_path).mkdir()
    link.symlink_to(outside)
    assert refusal(link, clips(tmp_path)) == f"{link} is outside {clips(tmp_path)}, where clips must be"


def test_a_file_without_an_audio_suffix_is_refused(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.txt", 1.0)
    assert refusal(clip, clips(tmp_path)).startswith(f"{clip} is not an audio file: its name must end with ")


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    clip = clips(tmp_path) / "missing.wav"
    assert refusal(clip, clips(tmp_path)) == f"{clip} is not a file"


def test_a_file_larger_than_allowed_is_refused(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.wav", 11.0)
    assert refusal(clip, clips(tmp_path)) == f"{clip} weighs over {LARGEST} bytes"


def test_a_file_that_is_not_audio_is_refused(tmp_path: Path) -> None:
    clip = clips(tmp_path) / "sample.mp3"
    clips(tmp_path).mkdir()
    _ = clip.write_text("not audio", encoding="utf-8")
    assert refusal(clip, clips(tmp_path)) == f"{clip} holds no audio FFmpeg can read"


def test_a_file_without_sound_is_refused(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.wav", 0.0)
    assert refusal(clip, clips(tmp_path)) == f"{clip} holds no sound"


def test_a_clip_longer_than_allowed_is_refused(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.wav", 3.0)
    assert refusal(clip, clips(tmp_path)) == f"{clip} lasts 3 s, over the {LONGEST:.0f} s allowed"


def test_a_clip_as_long_as_allowed_is_read(tmp_path: Path) -> None:
    clip = written(clips(tmp_path) / "sample.wav", LONGEST)
    assert len(read_clip(str(clip), rules=rules(clips(tmp_path)), rate=RATE)) == RATE * 2 * LONGEST
