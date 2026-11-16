from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.transport.abilities.carry.domain.received import Received


class Transport(Protocol):
    @property
    def rate(self) -> int: ...
    def play(self, pcm: bytes) -> None: ...
    def stop(self) -> None: ...
    async def carry(self, receive: Callable[[Received], Awaitable[None]], /) -> None: ...
