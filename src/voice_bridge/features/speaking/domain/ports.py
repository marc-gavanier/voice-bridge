from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class Decoder(Protocol):
    def __call__(self, path: Path, rate: int, /) -> bytes: ...
