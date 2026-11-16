from typing import Protocol


class Sound(Protocol):
    @property
    def pcm(self) -> bytes: ...
    @property
    def at(self) -> float: ...
    @property
    def frame_number(self) -> int: ...
