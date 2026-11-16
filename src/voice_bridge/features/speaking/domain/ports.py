from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

    from voice_bridge.features.speaking.domain.audio import Audio


class Decoder(Protocol):
    def __call__(self, location: str, rate: int, /) -> Iterator[bytes]: ...


class AudioSource(Protocol):
    def find(self, asked: str, /) -> Audio: ...
    def pick(self) -> Audio: ...
