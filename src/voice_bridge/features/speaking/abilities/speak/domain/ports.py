from typing import Protocol


class Pace(Protocol):
    def push(self, pcm: bytes, /) -> bytes: ...
    def end(self) -> bytes: ...


class Pacing(Protocol):
    def __call__(self, rate: int, factor: float, /) -> Pace: ...
