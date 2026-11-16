from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voice_bridge.features.speaking.domain.audio import AudioRefusedError
from voice_bridge.features.speaking.domain.ports import AudioSource, Decoder
from voice_bridge.features.speaking.implementation.audio_file import AudioFile

RATE = 48000
MUSIC = Path("/music/hold.mp3")


@dataclass
class RecordingDecoder:
    asked: list[tuple[str, int]] = field(default_factory=list)

    def __call__(self, location: str, rate: int, /) -> Iterator[bytes]:
        self.asked.append((location, rate))
        return iter([b"\x01\x00", b"\x02\x00"])


def source(decoder: Decoder) -> AudioSource:
    return AudioFile(path=MUSIC, decode=decoder, rate=RATE)


def test_the_file_picked_is_named_after_it() -> None:
    assert source(RecordingDecoder()).pick().name == "hold.mp3"


def test_the_file_picked_gives_the_frames_of_its_decoder() -> None:
    assert list(source(RecordingDecoder()).pick().frames) == [b"\x01\x00", b"\x02\x00"]


def test_the_file_picked_is_decoded_at_the_rate_of_the_source() -> None:
    decoder = RecordingDecoder()
    _ = source(decoder).pick()
    assert decoder.asked == [(str(MUSIC), RATE)]


def test_the_file_is_picked_again_once_played() -> None:
    decoder = RecordingDecoder()
    played = source(decoder)
    _ = (played.pick(), played.pick())
    assert decoder.asked == [(str(MUSIC), RATE), (str(MUSIC), RATE)]


def test_the_file_is_found_by_its_path() -> None:
    assert source(RecordingDecoder()).find(str(MUSIC)).name == "hold.mp3"


def test_another_file_is_refused() -> None:
    with pytest.raises(AudioRefusedError, match=r"^/music/other.mp3 is not /music/hold.mp3, the only file to play$"):
        _ = source(RecordingDecoder()).find("/music/other.mp3")
