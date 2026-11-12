from dataclasses import dataclass
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.domain.acknowledgement import fresh

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence


@dataclass(frozen=True, slots=True, kw_only=True)
class Candidates:
    pool: int
    sentences: tuple[str, ...]


def candidates(pools: Sequence[Collection[str]], kind: int | None, last: Mapping[int, str]) -> Candidates | None:
    if not pools:
        return None
    chosen = len(pools) - 1 if kind is None else kind
    pool = tuple(pools[chosen])
    if not pool:
        return None
    return Candidates(pool=chosen, sentences=fresh(pool, last.get(chosen)))
