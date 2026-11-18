from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

RANKED: Final = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    name: str
    threshold: float
    stops: bool = False
    answers: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Meaning:
    route: int | None
    score: float
    stops: bool
    answers: bool
    ranking: tuple[tuple[str, float], ...] = ()


def _ranking(scored: Sequence[tuple[float, Route]]) -> tuple[tuple[str, float], ...]:
    named = sorted(
        ((route.name, score) for score, route in scored),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return tuple(named[:RANKED])


def meaning_of(scores: Sequence[float], routes: Sequence[Route]) -> Meaning:
    scored = tuple(zip(scores, routes, strict=True))
    ranking = _ranking(scored)
    passing = [(score, index) for index, (score, route) in enumerate(scored) if score >= route.threshold]
    if not passing:
        return Meaning(route=None, score=max(scores, default=0.0), stops=False, answers=False, ranking=ranking)
    score, index = max(passing)
    route = routes[index]
    return Meaning(route=index, score=score, stops=route.stops, answers=route.answers, ranking=ranking)


def refused(tool: str, *, stopped: bool, allowed: frozenset[str]) -> bool:
    return stopped and tool not in allowed
