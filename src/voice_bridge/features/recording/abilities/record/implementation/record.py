import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio

from voice_bridge.features.recording.domain.take import Heard, Take, begin, extend, file_name, is_over, summary
from voice_bridge.libraries.audio.pcm import duration
from voice_bridge.libraries.audio.wav import encode

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Callable
    from pathlib import Path

    from voice_bridge.libraries.mumble.audio import Packet

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Recorder:
    directory: Path
    rate: int
    silence: float = 1.5


def _heard(recorder: Recorder, packet: Packet) -> Heard:
    return Heard(
        pcm=packet.pcm, at=packet.at, frame_number=packet.frame_number, duration=duration(packet.pcm, recorder.rate)
    )


def advance(recorder: Recorder, take: Take | None, tick: Packet | None, now: float) -> tuple[Take | None, Take | None]:
    finished = take if take is not None and is_over(take, now, recorder.silence) else None
    ongoing = None if finished else take
    if tick is None:
        return ongoing, finished
    heard = _heard(recorder, tick)
    return (extend(ongoing, heard) if ongoing else begin(heard)), finished


async def save(recorder: Recorder, take: Take) -> Path:
    path = recorder.directory / file_name(take)
    await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
    _ = await anyio.Path(path).write_bytes(encode(take.pcm, rate=recorder.rate))
    logger.info("%s: %s", path.name, summary(take, recorder.rate))
    return path


async def record(recorder: Recorder, ticks: AsyncIterable[Packet | None], clock: Callable[[], float]) -> None:
    take: Take | None = None
    async for tick in ticks:
        take, finished = advance(recorder, take, tick, clock())
        if finished:
            _ = await save(recorder, finished)
