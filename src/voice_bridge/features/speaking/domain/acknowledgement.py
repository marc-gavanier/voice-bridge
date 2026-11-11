from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def fresh(sentences: Sequence[str], last: str | None) -> tuple[str, ...]:
    others = tuple(sentence for sentence in sentences if sentence != last)
    return others or tuple(sentences)
