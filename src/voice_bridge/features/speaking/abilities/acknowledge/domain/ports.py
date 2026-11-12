from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class Draw(Protocol):
    def __call__(self, sentences: Sequence[str], /) -> str: ...
