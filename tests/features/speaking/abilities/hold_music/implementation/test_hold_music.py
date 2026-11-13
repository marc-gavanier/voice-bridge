from array import array
from dataclasses import dataclass, field

import numpy as np
import pytest

from voice_bridge.features.speaking.abilities.hold_music.domain.ports import Speaker
from voice_bridge.features.speaking.abilities.hold_music.implementation.hold_music import HoldMusic
from voice_bridge.features.speaking.domain.track import Track

pytestmark = pytest.mark.anyio

RATE = 2


class StoppedError(Exception):
    pass


@dataclass
class RecordedSpeaker:
    played: list[bytes] = field(default_factory=list)

    def play(self, pcm: bytes) -> None:
        self.played.append(pcm)


@dataclass
class Clock:
    sleeps: int
    slept: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        if len(self.slept) == self.sleeps:
            raise StoppedError
        self.slept.append(seconds)


def eight_bytes_for(speaker: Speaker) -> HoldMusic:
    return HoldMusic(track=Track(pcm=b"abcdefgh"), speaker=speaker, rate=RATE, chunk=0.5)


async def played(music: HoldMusic, sleeps: int) -> None:
    music.sleep = Clock(sleeps=sleeps)
    with pytest.raises(StoppedError):
        await music()


async def test_the_music_starts_one_chunk_ahead() -> None:
    speaker = RecordedSpeaker()
    await played(eight_bytes_for(speaker), sleeps=0)
    assert speaker.played == [b"ab", b"cd"]


async def test_the_music_goes_on_one_chunk_per_chunk_of_time() -> None:
    speaker = RecordedSpeaker()
    music = eight_bytes_for(speaker)
    await played(music, sleeps=2)
    assert speaker.played == [b"ab", b"cd", b"ef", b"gh"]


async def test_the_music_waits_a_chunk_of_time_between_chunks() -> None:
    music = eight_bytes_for(RecordedSpeaker())
    clock = Clock(sleeps=2)
    music.sleep = clock
    with pytest.raises(StoppedError):
        await music()
    assert clock.slept == [0.5, 0.5]


async def test_the_music_resumes_where_it_stopped() -> None:
    speaker = RecordedSpeaker()
    music = eight_bytes_for(speaker)
    await played(music, sleeps=0)
    await played(music, sleeps=0)
    assert speaker.played == [b"ab", b"cd", b"ef", b"gh"]


LOUD = np.full(8, 16384, dtype=np.int16).tobytes()


def loud_for(speaker: Speaker, *, fade_in: float = 0.0, fade_out: float = 0.0) -> HoldMusic:
    return HoldMusic(track=Track(pcm=LOUD), speaker=speaker, rate=RATE, chunk=1.0, fade_in=fade_in, fade_out=fade_out)


def samples_of(pcm: bytes) -> list[int]:
    return array("h", pcm).tolist()


async def test_the_music_fades_in_before_its_first_chunk() -> None:
    speaker = RecordedSpeaker()
    await played(loud_for(speaker, fade_in=2.0), sleeps=0)
    assert samples_of(speaker.played[0]) == [0, 5461, 10922, 16384]


async def test_without_a_fade_in_the_music_starts_whole() -> None:
    speaker = RecordedSpeaker()
    await played(loud_for(speaker), sleeps=0)
    assert samples_of(speaker.played[0]) == [16384, 16384]


def test_fading_out_plays_the_next_of_the_music_down_to_silence() -> None:
    speaker = RecordedSpeaker()
    loud_for(speaker, fade_out=2.0).fade()
    assert samples_of(speaker.played[0]) == [16384, 10922, 5461, 0]


def test_without_a_fade_out_stopping_plays_nothing_more() -> None:
    speaker = RecordedSpeaker()
    loud_for(speaker).fade()
    assert speaker.played == []
