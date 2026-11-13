import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anyio

from voice_bridge.features.speaking.domain.track import Track, next_chunk
from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES, ramp

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.speaking.abilities.hold_music.domain.ports import Speaker

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class HoldMusic:
    track: Track
    speaker: Speaker
    rate: int
    chunk: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    sleep: Callable[[float], Awaitable[None]] = field(default=anyio.sleep)

    def _next(self, seconds: float) -> bytes:
        pcm, self.track = next_chunk(self.track, round(self.rate * seconds) * SAMPLE_BYTES)
        return pcm

    def _feed(self) -> None:
        self.speaker.play(self._next(self.chunk))

    def fade(self) -> None:
        if self.fade_out > 0:
            self.speaker.play(ramp(self._next(self.fade_out), 1.0, 0.0))

    async def __call__(self) -> None:
        logger.info("hold music starts at %.1f s", self.track.position / SAMPLE_BYTES / self.rate)
        if self.fade_in > 0:
            self.speaker.play(ramp(self._next(self.fade_in), 0.0, 1.0))
        self._feed()
        while True:
            self._feed()
            await self.sleep(self.chunk)
