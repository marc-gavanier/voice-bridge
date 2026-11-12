from typing import Protocol


class Speaker(Protocol):
    def play(self, pcm: bytes) -> None: ...
