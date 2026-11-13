from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Wording:
    at_work: tuple[str, ...]
    many_at_work: str
    finished: tuple[str, ...]
    many_left: str
    none_at_work: str


def sentence_for(wording: Wording, at_work: int, *, finished: bool) -> str:
    if at_work < 1:
        return wording.none_at_work
    counted = wording.finished if finished else wording.at_work
    if at_work > len(counted):
        return wording.many_left if finished else wording.many_at_work
    return counted[at_work - 1]


def every_sentence(wording: Wording) -> tuple[str, ...]:
    return (*wording.at_work, wording.many_at_work, *wording.finished, wording.many_left, wording.none_at_work)
