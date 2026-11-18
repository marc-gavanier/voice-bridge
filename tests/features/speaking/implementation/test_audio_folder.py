import wave
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voice_bridge.features.speaking.domain.audio import AudioRefusedError
from voice_bridge.features.speaking.domain.ports import AudioSource
from voice_bridge.features.speaking.implementation.audio_folder import AudioFolder

RATE = 48000


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


def other_folder(tmp_path: Path) -> Path:
    return tmp_path / "music"


def source(directory: Path, decoder: RecordingDecoder | None = None) -> AudioSource:
    return AudioFolder(directories=(directory,), decode=decoder or RecordingDecoder(), rate=RATE)


def sources(*directories: Path) -> AudioSource:
    return AudioFolder(directories=directories, decode=RecordingDecoder(), rate=RATE)


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


def test_a_file_in_any_of_the_folders_is_found(tmp_path: Path) -> None:
    clip = written(other_folder(tmp_path) / "song.wav", 0.1)
    assert sources(folder(tmp_path), other_folder(tmp_path)).find(str(clip)).name == "song.wav"


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


def test_a_file_outside_every_folder_is_refused_with_the_folders_listed(tmp_path: Path) -> None:
    clip = written(tmp_path / "elsewhere" / "sample.wav", 0.1)
    with pytest.raises(AudioRefusedError) as refused:
        _ = sources(folder(tmp_path), other_folder(tmp_path)).find(str(clip))
    assert (
        str(refused.value) == f"{clip} is outside {folder(tmp_path)}, {other_folder(tmp_path)}, where the audio must be"
    )


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


@dataclass
class Draws:
    orders: list[tuple[str, ...]]

    def __call__(self, files: tuple[Path, ...], /) -> tuple[Path, ...]:
        by_name = {path.name: path for path in files}
        return tuple(by_name[name] for name in self.orders.pop(0))


def shuffled(*directories: Path, draws: Draws) -> AudioFolder:
    return AudioFolder(directories=directories, decode=RecordingDecoder(), rate=RATE, draw=draws)


def tracks(directory: Path, *names: str) -> Path:
    for name in names:
        _ = written(directory / name, 0.1)
    return directory


def names_of_picks(source: AudioSource, count: int) -> list[str]:
    return [source.pick().name for _ in range(count)]


def test_the_tracks_of_a_folder_are_picked_in_the_order_drawn(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "b.wav", "c.wav")
    assert names_of_picks(shuffled(directory, draws=Draws([("b.wav", "c.wav", "a.wav")])), 3) == [
        "b.wav",
        "c.wav",
        "a.wav",
    ]


def test_the_tracks_are_drawn_again_after_a_full_pass(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "b.wav", "c.wav")
    draws = Draws([("a.wav", "b.wav", "c.wav"), ("b.wav", "a.wav", "c.wav")])
    assert names_of_picks(shuffled(directory, draws=draws), 4) == ["a.wav", "b.wav", "c.wav", "b.wav"]


def test_a_new_pass_never_starts_with_the_track_that_just_played(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "b.wav")
    draws = Draws([("a.wav", "b.wav"), ("b.wav", "a.wav")])
    assert names_of_picks(shuffled(directory, draws=draws), 3) == ["a.wav", "b.wav", "a.wav"]


def test_the_tracks_of_subfolders_are_drawn_and_other_files_are_not(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "jazz/b.FLAC", "notes.txt")
    assert names_of_picks(shuffled(directory, draws=Draws([("a.wav", "b.FLAC")])), 2) == ["a.wav", "b.FLAC"]


def test_the_tracks_of_every_folder_are_drawn(tmp_path: Path) -> None:
    first, second = tracks(folder(tmp_path), "a.wav"), tracks(other_folder(tmp_path), "b.wav")
    assert names_of_picks(shuffled(first, second, draws=Draws([("b.wav", "a.wav")])), 2) == ["b.wav", "a.wav"]


def test_a_track_picked_is_decoded_at_the_rate_of_the_source(tmp_path: Path) -> None:
    track = written(folder(tmp_path) / "a.wav", 0.1)
    decoder = RecordingDecoder()
    _ = source(folder(tmp_path), decoder).pick()
    assert decoder.asked == [(str(track), RATE)]


def test_every_track_is_picked_once_in_a_pass_drawn_at_random(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "b.wav", "c.wav")
    assert sorted(names_of_picks(source(directory), 3)) == ["a.wav", "b.wav", "c.wav"]


def test_a_folder_named_like_a_track_is_not_drawn(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "a.wav", "b.wav/c.txt")
    assert names_of_picks(shuffled(directory, draws=Draws([("a.wav",), ("a.wav",)])), 2) == ["a.wav", "a.wav"]


def test_a_folder_without_a_track_is_refused(tmp_path: Path) -> None:
    directory = tracks(folder(tmp_path), "notes.txt")
    with pytest.raises(AudioRefusedError, match=f"^{directory} holds no audio file$"):
        _ = source(directory).pick()


def test_folders_without_a_track_are_refused_with_the_folders_listed(tmp_path: Path) -> None:
    first, second = tracks(folder(tmp_path), "notes.txt"), tracks(other_folder(tmp_path), "notes.txt")
    with pytest.raises(AudioRefusedError, match=f"^{first}, {second} holds no audio file$"):
        _ = sources(first, second).pick()
