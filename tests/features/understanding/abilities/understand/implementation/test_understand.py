from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from voice_bridge.features.understanding.abilities.understand.domain.ports import Scores
from voice_bridge.features.understanding.abilities.understand.implementation.understand import (
    StopFlag,
    Understanding,
)
from voice_bridge.features.understanding.domain.meaning import Meaning, Route

ROUTES = (Route(name="stop", threshold=0.75, stops=True), Route(name="yes", threshold=0.5))
STOP = Meaning(route=0, score=0.9, stops=True, answers=False, ranking=(("stop", 0.9), ("yes", 0.2)))
YES = Meaning(route=1, score=0.8, stops=False, answers=False, ranking=(("yes", 0.8), ("stop", 0.1)))
ALLOWED = frozenset({"mcp__voice__reply"})


@dataclass
class KeywordScores:
    asked: list[str] = field(default_factory=list)

    def __call__(self, text: str) -> Sequence[float]:
        self.asked.append(text)
        return (0.9, 0.2) if "stop" in text.lower() else (0.1, 0.8)


def understanding(scores: Scores) -> Understanding:
    return Understanding(scores=scores, routes=ROUTES)


def test_words_are_understood_from_their_scores() -> None:
    assert understanding(KeywordScores())("Stop.") == STOP


def test_words_are_scored_without_their_surrounding_spaces() -> None:
    scores = KeywordScores()
    _ = understanding(scores)("  Oui.  ")
    assert scores.asked == ["Oui."]


def test_the_same_words_are_scored_once() -> None:
    scores = KeywordScores()
    understood = understanding(scores)
    _ = understood("Oui.")
    _ = understood("Oui.")
    assert scores.asked == ["Oui."]


def test_new_words_are_scored_again() -> None:
    understood = understanding(KeywordScores())
    _ = understood("Stop.")
    assert understood("Oui.") == YES


def test_words_close_to_no_route_are_understood_as_nothing() -> None:
    understood = Understanding(
        scores=KeywordScores(), routes=(Route(name="stop", threshold=0.95, stops=True), ROUTES[1])
    )
    assert understood("Stop.").route is None


def test_a_stop_raises_the_flag(tmp_path: Path) -> None:
    flag = StopFlag(tmp_path / "runtime" / "stop")
    flag.follow(STOP)
    assert flag.path.exists()


def test_a_stop_after_a_stop_keeps_the_flag(tmp_path: Path) -> None:
    flag = StopFlag(tmp_path / "stop")
    flag.follow(STOP)
    flag.follow(STOP)
    assert flag.path.exists()


def test_the_next_message_lowers_the_flag(tmp_path: Path) -> None:
    flag = StopFlag(tmp_path / "stop")
    flag.follow(STOP)
    flag.follow(YES)
    assert not flag.path.exists()


def test_a_message_without_a_flag_leaves_none(tmp_path: Path) -> None:
    flag = StopFlag(tmp_path / "stop")
    flag.follow(YES)
    assert not flag.path.exists()
