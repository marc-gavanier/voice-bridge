from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator


class Decoder(Protocol):
    def __call__(self, location: str, rate: int, /) -> Iterator[bytes]: ...
