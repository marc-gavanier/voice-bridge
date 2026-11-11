from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import re
    from collections.abc import Sequence


def kind_of(words: str, patterns: Sequence[re.Pattern[str]]) -> int | None:
    stripped = words.strip()
    return next((index for index, pattern in enumerate(patterns) if pattern.search(stripped)), None)


def fresh(sentences: Sequence[str], last: str | None) -> tuple[str, ...]:
    others = tuple(sentence for sentence in sentences if sentence != last)
    return others or tuple(sentences)
