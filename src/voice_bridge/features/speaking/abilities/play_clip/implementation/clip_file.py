import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import anyio

from voice_bridge.features.speaking.domain.audio import AudioRefusedError
from voice_bridge.libraries.audio.pcm import duration, scaled

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from voice_bridge.features.speaking.domain.ports import AudioSource

PIECE: Final = 0.5
AHEAD: Final = 5.0

logger = logging.getLogger(__name__)


class ClipRefusedError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Pace:
    ahead: float = AHEAD
    clock: Callable[[], float] = anyio.current_time
    sleep: Callable[[float], Awaitable[None]] = anyio.sleep


def check_clip(path: str, *, source: AudioSource) -> None:
    audio = source.find(path)
    try:
        first = next((frame for frame in audio.frames if frame), b"")
    except ValueError as error:
        message = f"{path} holds no audio FFmpeg can read"
        raise ClipRefusedError(message) from error
    if not first:
        message = f"{path} holds no sound"
        raise ClipRefusedError(message)


def _next_piece(frames: Iterator[bytes], size: int) -> bytes:
    piece = bytearray()
    for frame in frames:
        piece += frame
        if len(piece) >= size:
            break
    return bytes(piece)


@dataclass(frozen=True, slots=True, kw_only=True)
class ClipStream:
    source: AudioSource
    volume: float
    rate: int
    pace: Pace = field(default_factory=Pace)

    async def __call__(self, path: str, hear: Callable[[bytes], Awaitable[None]], /) -> bool:
        try:
            audio = await anyio.to_thread.run_sync(self.source.find, path)
        except AudioRefusedError as error:
            logger.warning("clip no longer played: %s", error)
            return False
        size = 2 * max(1, round(PIECE * self.rate))
        started, sent = self.pace.clock(), 0.0
        try:
            while piece := await anyio.to_thread.run_sync(_next_piece, audio.frames, size):
                await self.pace.sleep(max(0.0, started + sent - self.pace.ahead - self.pace.clock()))
                await hear(scaled(piece, self.volume))
                sent += duration(piece, self.rate)
        except ValueError as error:
            logger.warning("clip cut short: %s", error)
            return False
        return True
