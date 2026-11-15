from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from voice_bridge.features.speaking.domain.acknowledgement import fresh

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

NEUTRAL: Final = "neutral"
NEUTRAL_QUESTION: Final = "neutral_question"
QUESTION_MARKS: Final = frozenset({"?", "\N{FULLWIDTH QUESTION MARK}", "\N{ARABIC QUESTION MARK}"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidates:
    pool: int
    sentences: tuple[str, ...]


def fallback(words: str) -> str:
    return NEUTRAL_QUESTION if words.rstrip()[-1:] in QUESTION_MARKS else NEUTRAL


def pool_of(route: int | None, words: str, *, routes: int) -> int:
    if route is not None:
        return route
    return routes + 1 if fallback(words) == NEUTRAL_QUESTION else routes


def candidates(pools: Sequence[Collection[str]], kind: int | None, last: str | None) -> Candidates | None:
    if not pools:
        return None
    chosen = len(pools) - 1 if kind is None else kind
    pool = tuple(pools[chosen])
    if not pool:
        return None
    return Candidates(pool=chosen, sentences=fresh(pool, last))
