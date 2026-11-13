from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from voice_bridge.features.conversation.domain.turn_trace import Report


class Claude(Protocol):
    async def __call__(self, text: str, *, interrupted: bool, acknowledgement: str | None) -> None: ...


class Acknowledgement(Protocol):
    def __call__(self, words: str) -> tuple[str, bytes] | None: ...


class Announcement(Protocol):
    def __call__(self, at_work: int, *, finished: bool) -> tuple[str, bytes] | None: ...


class Speaker(Protocol):
    def play(self, pcm: bytes) -> None: ...
    def stop(self) -> None: ...


class HoldMusic(Protocol):
    async def __call__(self) -> None: ...
    def fade(self) -> None: ...


class Telemetry(Protocol):
    def __call__(self, report: Report, /) -> None: ...
