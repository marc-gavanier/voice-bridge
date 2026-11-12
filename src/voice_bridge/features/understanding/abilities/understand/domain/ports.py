from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class Scores(Protocol):
    def __call__(self, text: str) -> Sequence[float]: ...
