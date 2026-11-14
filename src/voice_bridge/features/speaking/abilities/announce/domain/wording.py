from dataclasses import dataclass
from typing import Final

FIRST_COUNTED: Final = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class Wording:
    at_work: tuple[str, ...]
    many_at_work: str


def sentence_for(wording: Wording, at_work: int) -> str | None:
    if at_work < FIRST_COUNTED:
        return None
    rank = at_work - FIRST_COUNTED
    return wording.at_work[rank] if rank < len(wording.at_work) else wording.many_at_work


def every_sentence(wording: Wording) -> tuple[str, ...]:
    return (*wording.at_work, wording.many_at_work)
