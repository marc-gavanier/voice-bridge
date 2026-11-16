import wave
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voice_bridge.features.speaking.domain.audio import AudioRefusedError
from voice_bridge.features.speaking.implementation.audio_folder import AudioFolder

RATE = 48000
LARGEST = 1_000_000


@dataclass
class RecordingDecoder:
    asked: list[tuple[str, int]] = field(default_factory=list)

    def __call__(self, location: str, rate: int, /) -> Iterator[bytes]:
        self.asked.append((location, rate))
        return iter([b"\x01\x00"])


def written(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(bytes(int(RATE * seconds) * 2))
    return path


def folder(tmp_path: Path) -> Path:
    return tmp_path / "clips"


def source(directory: Path, decoder: RecordingDecoder | None = None) -> AudioFolder:
    return AudioFolder(directory=directory, largest=LARGEST, decode=decoder or RecordingDecoder(), rate=RATE)


def refusal(path: Path | str, directory: Path) -> str:
    with pytest.raises(AudioRefusedError) as refused:
        _ = source(directory).find(str(path))
    return str(refused.value)


def test_a_file_in_the_folder_is_found_by_its_name(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "sample.wav", 0.1)
    assert source(folder(tmp_path)).find(str(clip)).name == "sample.wav"


def test_a_file_found_gives_the_frames_of_its_decoder(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "sample.wav", 0.1)
    assert list(source(folder(tmp_path)).find(str(clip)).frames) == [b"\x01\x00"]


def test_a_file_found_is_decoded_from_its_resolved_path_at_the_rate_of_the_source(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "sample.wav", 0.1)
    decoder = RecordingDecoder()
    _ = source(folder(tmp_path), decoder).find(str(clip))
    assert decoder.asked == [(str(clip.resolve()), RATE)]


def test_a_file_in_a_subfolder_is_found(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "comparison" / "sample.wav", 0.1)
    assert source(folder(tmp_path)).find(str(clip)).name == "sample.wav"


def test_a_file_with_an_upper_case_suffix_is_found(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "SAMPLE.WAV", 0.1)
    assert source(folder(tmp_path)).find(str(clip)).name == "SAMPLE.WAV"


def test_a_relative_path_is_refused(tmp_path: Path) -> None:
    _ = written(folder(tmp_path) / "sample.wav", 0.1)
    assert refusal("sample.wav", folder(tmp_path)) == "sample.wav is not an absolute path"


def test_a_file_outside_the_folder_is_refused(tmp_path: Path) -> None:
    clip = written(tmp_path / "elsewhere" / "sample.wav", 0.1)
    assert refusal(clip, folder(tmp_path)) == f"{clip} is outside {folder(tmp_path)}, where the audio must be"


def test_a_path_climbing_out_of_the_folder_is_refused(tmp_path: Path) -> None:
    _ = written(tmp_path / "sample.wav", 0.1)
    climbing = folder(tmp_path) / ".." / "sample.wav"
    folder(tmp_path).mkdir()
    assert refusal(climbing, folder(tmp_path)) == f"{climbing} is outside {folder(tmp_path)}, where the audio must be"


def test_a_link_in_the_folder_to_a_file_outside_is_refused(tmp_path: Path) -> None:
    outside = written(tmp_path / "sample.wav", 0.1)
    link = folder(tmp_path) / "link.wav"
    folder(tmp_path).mkdir()
    link.symlink_to(outside)
    assert refusal(link, folder(tmp_path)) == f"{link} is outside {folder(tmp_path)}, where the audio must be"


def test_a_file_without_an_audio_suffix_is_refused(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "sample.txt", 0.1)
    assert refusal(clip, folder(tmp_path)).startswith(f"{clip} is not an audio file: its name must end with .aac, ")


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    clip = folder(tmp_path) / "missing.wav"
    assert refusal(clip, folder(tmp_path)) == f"{clip} is not a file"


def test_a_file_larger_than_allowed_is_refused(tmp_path: Path) -> None:
    clip = written(folder(tmp_path) / "sample.wav", 11.0)
    assert refusal(clip, folder(tmp_path)) == f"{clip} weighs over {LARGEST} bytes"
