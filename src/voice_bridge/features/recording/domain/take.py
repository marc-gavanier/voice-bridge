from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePath
from typing import Final

FRAME_DURATION: Final = 0.01


@dataclass(frozen=True, slots=True, kw_only=True)
class Heard:
    pcm: bytes
    at: float
    frame_number: int
    duration: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Take:
    chunks: tuple[bytes, ...]
    start: float
    last: float
    expected: int
    lost: float
    longest_gap: float

    @property
    def pcm(self) -> bytes:
        return b"".join(self.chunks)


def _next_frame(heard: Heard) -> int:
    return heard.frame_number + round(heard.duration / FRAME_DURATION)


def begin(heard: Heard) -> Take:
    return Take(
        chunks=(heard.pcm,), start=heard.at, last=heard.at, expected=_next_frame(heard), lost=0.0, longest_gap=0.0
    )


def extend(take: Take, heard: Heard) -> Take:
    return replace(
        take,
        chunks=(*take.chunks, heard.pcm),
        last=heard.at,
        expected=_next_frame(heard),
        lost=take.lost + max(0, heard.frame_number - take.expected) * FRAME_DURATION,
        longest_gap=max(take.longest_gap, heard.at - take.last),
    )


def is_over(take: Take, now: float, silence: float) -> bool:
    return now - take.last > silence


def advance(take: Take | None, heard: Heard | None, now: float, silence: float) -> tuple[Take | None, Take | None]:
    finished = take if take is not None and is_over(take, now, silence) else None
    ongoing = None if finished else take
    if heard is None:
        return ongoing, finished
    return (extend(ongoing, heard) if ongoing else begin(heard)), finished


def file_name(take: Take) -> PurePath:
    started = datetime.fromtimestamp(take.start).astimezone()
    return PurePath(f"{started:%Y-%m-%d}", f"{started:%H%M%S}.wav")


def summary(take: Take, rate: int) -> str:
    seconds = len(take.pcm) / 2 / rate
    lost, gap = round(take.lost * 1000), round(take.longest_gap * 1000)
    return f"{seconds:.1f}s, {len(take.chunks)} packets, {lost} ms lost, longest gap {gap} ms"
