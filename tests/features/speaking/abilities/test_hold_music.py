from dataclasses import dataclass, field

import pytest

from voice_bridge.features.speaking.abilities.hold_music import HoldMusic
from voice_bridge.features.speaking.domain.track import Track

pytestmark = pytest.mark.anyio

RATE = 2


class StoppedError(Exception):
    pass


@dataclass
class Speaker:
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


async def played(music: HoldMusic, sleeps: int) -> None:
    music.sleep = Clock(sleeps=sleeps)
    with pytest.raises(StoppedError):
        await music()


async def test_the_music_starts_one_chunk_ahead() -> None:
    speaker = Speaker()
    await played(HoldMusic(track=Track(pcm=b"abcdefgh"), speaker=speaker, rate=RATE, chunk=0.5), sleeps=0)
    assert speaker.played == [b"ab", b"cd"]


async def test_the_music_goes_on_one_chunk_per_chunk_of_time() -> None:
    speaker = Speaker()
    music = HoldMusic(track=Track(pcm=b"abcdefgh"), speaker=speaker, rate=RATE, chunk=0.5)
    await played(music, sleeps=2)
    assert speaker.played == [b"ab", b"cd", b"ef", b"gh"]


async def test_the_music_waits_a_chunk_of_time_between_chunks() -> None:
    music = HoldMusic(track=Track(pcm=b"abcdefgh"), speaker=Speaker(), rate=RATE, chunk=0.5)
    clock = Clock(sleeps=2)
    music.sleep = clock
    with pytest.raises(StoppedError):
        await music()
    assert clock.slept == [0.5, 0.5]


async def test_the_music_resumes_where_it_stopped() -> None:
    speaker = Speaker()
    music = HoldMusic(track=Track(pcm=b"abcdefgh"), speaker=speaker, rate=RATE, chunk=0.5)
    await played(music, sleeps=0)
    await played(music, sleeps=0)
    assert speaker.played == [b"ab", b"cd", b"ef", b"gh"]
