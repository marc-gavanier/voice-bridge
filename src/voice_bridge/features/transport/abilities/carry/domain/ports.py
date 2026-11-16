from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.transport.abilities.carry.domain.received import Received


class Outgoing(Protocol):
    def __call__(self, size: int, /) -> bytes: ...


class Transport(Protocol):
    @property
    def rate(self) -> int: ...
    async def carry(self, receive: Callable[[Received], Awaitable[None]], outgoing: Outgoing, /) -> None: ...
