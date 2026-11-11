import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import anyio

from voice_bridge.features.speaking.domain.track import Track, next_chunk
from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class Speaker(Protocol):
    def play(self, pcm: bytes) -> None: ...


@dataclass(slots=True, kw_only=True)
class HoldMusic:
    track: Track
    speaker: Speaker
    rate: int
    chunk: float = 1.0
    sleep: Callable[[float], Awaitable[None]] = field(default=anyio.sleep)

    def _feed(self) -> None:
        pcm, self.track = next_chunk(self.track, round(self.rate * self.chunk) * SAMPLE_BYTES)
        self.speaker.play(pcm)

    async def __call__(self) -> None:
        logger.info("hold music starts at %.1f s", self.track.position / SAMPLE_BYTES / self.rate)
        self._feed()
        while True:
            self._feed()
            await self.sleep(self.chunk)
