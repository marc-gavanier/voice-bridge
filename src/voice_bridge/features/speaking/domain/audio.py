from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class AudioRefusedError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Audio:
    name: str
    frames: Iterator[bytes]
