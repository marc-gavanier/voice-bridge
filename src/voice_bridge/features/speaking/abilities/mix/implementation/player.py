import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.abilities.mix.domain.mixing import Layer, Mix, pull, queue, queued
from voice_bridge.features.speaking.abilities.mix.domain.played import Played

if TYPE_CHECKING:
    from collections.abc import Callable

    from voice_bridge.features.speaking.abilities.mix.domain.ports import Reference

logger = logging.getLogger(__name__)


def _unheard(_played: Played, /) -> None:
    return None


@dataclass(slots=True, kw_only=True)
class Player:
    clock: Callable[[], float]
    reference: Reference = field(default=_unheard)
    mix: Mix = field(default_factory=Mix)

    def play(self, layer: Layer, pcm: bytes) -> None:
        if not queued(self.mix):
            logger.info("playback starts")
        self.mix = queue(self.mix, layer, pcm)

    def stop(self) -> None:
        self.mix = Mix()

    def __call__(self, size: int, /) -> bytes:
        pcm, self.mix = pull(self.mix, size)
        if pcm:
            self.reference(Played(pcm=pcm, at=self.clock()))
        return pcm

    def channel(self, layer: Layer) -> Channel:
        return Channel(player=self, layer=layer)


@dataclass(frozen=True, slots=True, kw_only=True)
class Channel:
    player: Player
    layer: Layer

    def play(self, pcm: bytes) -> None:
        self.player.play(self.layer, pcm)

    def stop(self) -> None:
        self.player.stop()
