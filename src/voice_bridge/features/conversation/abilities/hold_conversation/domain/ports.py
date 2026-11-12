from typing import Protocol


class Claude(Protocol):
    async def __call__(self, text: str, *, interrupted: bool, acknowledgement: str | None) -> None: ...


class Acknowledgement(Protocol):
    def __call__(self, words: str) -> tuple[str, bytes] | None: ...


class Speaker(Protocol):
    def play(self, pcm: bytes) -> None: ...
    def stop(self) -> None: ...
