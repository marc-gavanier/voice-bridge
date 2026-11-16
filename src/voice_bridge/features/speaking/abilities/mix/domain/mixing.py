from array import array
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from itertools import zip_longest
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

PEAK: Final = 32767
TROUGH: Final = -32768


class Layer(Enum):
    VOICE = auto()
    MUSIC = auto()


@dataclass(frozen=True, slots=True, kw_only=True)
class Sound:
    pcm: bytes = b""
    position: int = 0
    start: int = 0

    @property
    def left(self) -> int:
        return len(self.pcm) - self.position

    @property
    def end(self) -> int:
        return self.start + self.left if self.left else 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Mix:
    layers: Mapping[Layer, Sound] = field(default_factory=dict[Layer, Sound])


def queued(mix: Mix) -> int:
    return max((sound.end for sound in mix.layers.values()), default=0)


def queue(mix: Mix, layer: Layer, pcm: bytes) -> Mix:
    sound = mix.layers.get(layer, Sound())
    following = (
        replace(sound, pcm=sound.pcm[sound.position :] + pcm, position=0)
        if sound.left
        else Sound(pcm=pcm, start=queued(mix))
    )
    return Mix(layers={**mix.layers, layer: following})


def _window(sound: Sound, size: int) -> array[int]:
    lead = min(sound.start, size)
    return array("h", bytes(lead) + sound.pcm[sound.position : sound.position + size - lead])


def _after(sound: Sound, size: int) -> Sound:
    lead = min(sound.start, size)
    return replace(sound, position=min(len(sound.pcm), sound.position + size - lead), start=sound.start - lead)


def _clipped(*column: int) -> int:
    return max(TROUGH, min(PEAK, sum(column)))


def _summed(windows: list[array[int]]) -> bytes:
    return array("h", (_clipped(*column) for column in zip_longest(*windows, fillvalue=0))).tobytes()


def pull(mix: Mix, size: int) -> tuple[bytes, Mix]:
    if queued(mix) < size:
        return b"", mix
    windows = [_window(sound, size) for sound in mix.layers.values()]
    return _summed(windows), Mix(layers={layer: _after(sound, size) for layer, sound in mix.layers.items()})
