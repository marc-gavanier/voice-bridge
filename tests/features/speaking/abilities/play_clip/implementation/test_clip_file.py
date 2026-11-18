from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import numpy as np
import pytest

from voice_bridge.features.speaking.abilities.play_clip.implementation.clip_file import (
    ClipRefusedError,
    ClipStream,
    Pace,
    check_clip,
)
from voice_bridge.features.speaking.domain.audio import Audio, AudioRefusedError
from voice_bridge.libraries.audio.pcm import level

RATE = 48000
CLIP = "/clips/sample.wav"
HALF_SECOND = RATE

pytestmark = pytest.mark.anyio


def tone(seconds: float) -> bytes:
    return (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(RATE * seconds))) * 16000).astype(np.int16).tobytes()


class Unreadable:
    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        message = "Invalid data found when processing input"
        raise ValueError(message)


def broken_after(*pieces: bytes) -> Iterator[bytes]:
    yield from pieces
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


@dataclass
class Clock:
    now: float = 0.0
    slept: list[float] = field(default_factory=list)

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class Heard:
    pieces: list[bytes] = field(default_factory=list)

    async def __call__(self, pcm: bytes) -> None:
        self.pieces.append(pcm)


def stream(source: FoundSource | RefusingSource, *, volume: float = 1.0, clock: Clock | None = None) -> ClipStream:
    timing = clock or Clock()
    return ClipStream(
        source=source, volume=volume, rate=RATE, pace=Pace(ahead=1.0, clock=timing.time, sleep=timing.sleep)
    )


async def heard(source: FoundSource | RefusingSource, *, volume: float = 1.0, clock: Clock | None = None) -> Heard:
    hear = Heard()
    _ = await stream(source, volume=volume, clock=clock)(CLIP, hear)
    return hear


async def played(source: FoundSource | RefusingSource) -> bool:
    return await stream(source)(CLIP, Heard())


def test_a_clip_with_sound_is_accepted() -> None:
    check_clip(CLIP, source=holding(tone(0.5)))


def test_a_clip_is_checked_in_its_source() -> None:
    source = holding(tone(0.5))
    check_clip(CLIP, source=source)
    assert source.asked == [CLIP]


def test_a_clip_whose_sound_follows_empty_frames_is_accepted() -> None:
    check_clip(CLIP, source=holding(b"", tone(0.5)))


def test_a_clip_the_source_refuses_is_refused_with_its_reason() -> None:
    with pytest.raises(AudioRefusedError, match=f"^{CLIP} is not a file$"):
        check_clip(CLIP, source=RefusingSource())


def test_a_clip_the_decoder_cannot_read_is_refused() -> None:
    with pytest.raises(ClipRefusedError, match=f"^{CLIP} holds no audio FFmpeg can read$"):
        check_clip(CLIP, source=FoundSource(frames=Unreadable))


def test_a_clip_without_sound_is_refused() -> None:
    with pytest.raises(ClipRefusedError, match=f"^{CLIP} holds no sound$"):
        check_clip(CLIP, source=holding(b""))


async def test_a_clip_is_heard_whole() -> None:
    hear = await heard(holding(tone(0.3), tone(0.4)))
    assert b"".join(hear.pieces) == tone(0.3) + tone(0.4)


async def test_a_clip_is_heard_in_pieces_of_half_a_second() -> None:
    hear = await heard(holding(*[tone(0.1)] * 12))
    assert [len(piece) for piece in hear.pieces] == [HALF_SECOND, HALF_SECOND, HALF_SECOND * 2 // 5]


async def test_a_clip_is_found_in_its_source_when_it_plays() -> None:
    source = holding(tone(0.5))
    _ = await played(source)
    assert source.asked == [CLIP]


async def test_a_clip_is_heard_at_the_volume_set() -> None:
    hear = await heard(holding(tone(0.5)), volume=0.25)
    assert level(hear.pieces[0]) == pytest.approx(level(tone(0.5)) / 4, rel=0.01)


async def test_a_clip_heard_to_its_end_has_played() -> None:
    assert await played(holding(tone(0.5)))


async def test_a_clip_the_source_now_refuses_is_not_played() -> None:
    assert not await played(RefusingSource())


async def test_a_clip_the_source_now_refuses_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    _ = await played(RefusingSource())
    assert f"clip no longer played: {CLIP} is not a file" in caplog.text


async def test_a_clip_the_decoder_breaks_in_is_cut_short() -> None:
    assert not await played(FoundSource(frames=lambda: broken_after(tone(0.5))))


async def test_a_clip_cut_short_keeps_what_was_heard() -> None:
    hear = await heard(FoundSource(frames=lambda: broken_after(tone(0.5))))
    assert hear.pieces == [tone(0.5)]


async def test_a_clip_cut_short_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    _ = await played(FoundSource(frames=lambda: broken_after(tone(0.5))))
    assert "clip cut short: Invalid data found when processing input" in caplog.text


async def test_a_clip_is_sent_without_waiting_while_it_stays_within_the_lead() -> None:
    clock = Clock()
    _ = await heard(holding(tone(0.5), tone(0.5), tone(0.5)), clock=clock)
    assert clock.slept == [0.0, 0.0, 0.0]


async def test_a_clip_waits_once_it_is_further_ahead_than_the_lead() -> None:
    clock = Clock()
    _ = await heard(holding(*[tone(0.5)] * 4), clock=clock)
    assert clock.slept == [0.0, 0.0, 0.0, 0.5]
