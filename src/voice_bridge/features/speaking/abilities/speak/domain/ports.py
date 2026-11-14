from typing import Protocol


class Stretch(Protocol):
    def __call__(self, pcm: bytes, rate: int, factor: float, /) -> bytes: ...
