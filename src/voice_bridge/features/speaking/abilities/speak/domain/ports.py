from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class SynthesisError(Exception):
    pass


class Pace(Protocol):
    def push(self, pcm: bytes, /) -> bytes: ...
    def end(self) -> bytes: ...


class Pacing(Protocol):
    def __call__(self, rate: int, factor: float, /) -> Pace: ...


class Synthesis(Protocol):
    @property
    def fingerprint(self) -> str: ...
    async def whole(self, sentence: str, /) -> bytes: ...
    async def stream(self, sentence: str, hear: Callable[[bytes], Awaitable[None]], /) -> None: ...
    async def ready(self) -> bool: ...
