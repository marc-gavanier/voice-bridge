from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    name: str
    threshold: float
    stops: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Meaning:
    route: int | None
    score: float
    stops: bool


def meaning_of(scores: Sequence[float], routes: Sequence[Route]) -> Meaning:
    passing = [
        (score, index)
        for index, (score, route) in enumerate(zip(scores, routes, strict=True))
        if score >= route.threshold
    ]
    if not passing:
        return Meaning(route=None, score=max(scores, default=0.0), stops=False)
    score, index = max(passing)
    return Meaning(route=index, score=score, stops=routes[index].stops)


def refused(tool: str, *, stopped: bool, allowed: frozenset[str]) -> bool:
    return stopped and tool not in allowed
