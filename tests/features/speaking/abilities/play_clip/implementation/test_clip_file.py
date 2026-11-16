from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import numpy as np
import pytest

from voice_bridge.features.speaking.abilities.play_clip.implementation.clip_file import (
    ClipRefusedError,
    ClipRules,
    read_clip,
)
from voice_bridge.features.speaking.domain.audio import Audio, AudioRefusedError
from voice_bridge.libraries.audio.pcm import level

RATE = 48000
LONGEST = 2.0
CLIP = "/clips/sample.wav"


def tone(seconds: float) -> bytes:
    return (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(RATE * seconds))) * 16000).astype(np.int16).tobytes()


class Unreadable:
    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        message = "Invalid data found when processing input"
        raise ValueError(message)


@dataclass
class FoundSource:
    frames: Callable[[], Iterator[bytes]]
    asked: list[str] = field(default_factory=list)

    def find(self, asked: str, /) -> Audio:
        self.asked.append(asked)
        return Audio(name="sample.wav", frames=self.frames())

    def pick(self) -> Audio:
        return self.find(CLIP)


def holding(*pieces: bytes) -> FoundSource:
    return FoundSource(frames=lambda: iter(pieces))


class RefusingSource:
    def find(self, asked: str, /) -> Audio:
        message = f"{asked} is not a file"
        raise AudioRefusedError(message)

    def pick(self) -> Audio:
        return self.find(CLIP)


def read(source: FoundSource | RefusingSource, *, volume: float = 1.0) -> bytes:
    return read_clip(CLIP, source=source, rules=ClipRules(longest=LONGEST, volume=volume), rate=RATE)


def test_a_clip_is_read_as_the_frames_of_its_source_joined() -> None:
    assert read(holding(tone(0.5), tone(0.25))) == tone(0.5) + tone(0.25)


def test_the_clip_asked_is_found_in_the_source() -> None:
    source = holding(tone(0.5))
    _ = read(source)
    assert source.asked == [CLIP]


def test_a_clip_is_read_at_the_volume_set() -> None:
    soft = level(read(holding(tone(0.5)), volume=0.25))
    assert soft == pytest.approx(level(tone(0.5)) / 4, rel=0.01)


def test_a_clip_the_source_refuses_is_refused_with_its_reason() -> None:
    with pytest.raises(AudioRefusedError, match=f"^{CLIP} is not a file$"):
        _ = read(RefusingSource())


def test_a_clip_the_decoder_cannot_read_is_refused() -> None:
    with pytest.raises(ClipRefusedError, match=f"^{CLIP} holds no audio FFmpeg can read$"):
        _ = read(FoundSource(frames=Unreadable))


def test_a_clip_without_sound_is_refused() -> None:
    with pytest.raises(ClipRefusedError, match=f"^{CLIP} holds no sound$"):
        _ = read(holding())


def test_a_clip_longer_than_allowed_is_refused() -> None:
    with pytest.raises(ClipRefusedError, match=f"^{CLIP} lasts 3 s, over the {LONGEST:.0f} s allowed$"):
        _ = read(holding(tone(3.0)))


def test_a_clip_as_long_as_allowed_is_read() -> None:
    assert read(holding(tone(LONGEST))) == tone(LONGEST)
