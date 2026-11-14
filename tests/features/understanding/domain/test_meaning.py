import pytest

from voice_bridge.features.understanding.domain.meaning import RANKED, Meaning, Route, meaning_of, refused

ROUTES = (
    Route(name="stop", threshold=0.75, stops=True),
    Route(name="yes", threshold=0.5),
    Route(name="question", threshold=0.5),
)
ANSWERED_ROUTES = (Route(name="yes", threshold=0.5), Route(name="presence", threshold=0.5, answers=True))
MANY_ROUTES = (*ROUTES, Route(name="thanks", threshold=0.5))


def test_the_closest_route_above_its_threshold_is_chosen() -> None:
    assert meaning_of((0.2, 0.6, 0.9), ROUTES) == Meaning(
        route=2, score=0.9, stops=False, answers=False, ranking=(("question", 0.9), ("yes", 0.6), ("stop", 0.2))
    )


def test_a_route_asking_to_stop_carries_the_stop() -> None:
    assert meaning_of((0.8, 0.6, 0.3), ROUTES).stops


def test_a_route_its_acknowledgement_answers_carries_the_answer() -> None:
    assert meaning_of((0.2, 0.9), ANSWERED_ROUTES).answers


def test_a_route_its_acknowledgement_does_not_answer_carries_no_answer() -> None:
    assert not meaning_of((0.9, 0.2), ANSWERED_ROUTES).answers


def test_a_score_equal_to_the_threshold_passes() -> None:
    assert meaning_of((0.75, 0.1, 0.1), ROUTES).route == 0


def test_a_closer_route_below_its_own_threshold_gives_way_to_the_next() -> None:
    assert meaning_of((0.7, 0.6, 0.3), ROUTES) == Meaning(
        route=1, score=0.6, stops=False, answers=False, ranking=(("stop", 0.7), ("yes", 0.6), ("question", 0.3))
    )


def test_words_close_to_no_route_have_no_route() -> None:
    assert meaning_of((0.7, 0.4, 0.3), ROUTES) == Meaning(
        route=None, score=0.7, stops=False, answers=False, ranking=(("stop", 0.7), ("yes", 0.4), ("question", 0.3))
    )


def test_no_route_means_no_route_and_no_stop() -> None:
    assert meaning_of((), ()) == Meaning(route=None, score=0.0, stops=False, answers=False)


def test_only_the_closest_routes_are_ranked() -> None:
    assert len(meaning_of((0.1, 0.2, 0.3, 0.4), MANY_ROUTES).ranking) == RANKED


def test_the_ranking_leaves_out_the_farthest_route() -> None:
    assert [name for name, _ in meaning_of((0.1, 0.2, 0.3, 0.4), MANY_ROUTES).ranking] == ["thanks", "question", "yes"]


def test_routes_as_close_keep_their_order_in_the_ranking() -> None:
    assert [name for name, _ in meaning_of((0.5, 0.5, 0.5), ROUTES).ranking] == ["stop", "yes", "question"]


def test_a_tool_is_refused_after_a_stop() -> None:
    assert refused("Bash", stopped=True, allowed=frozenset({"mcp__voice__reply"}))


def test_an_allowed_tool_runs_after_a_stop() -> None:
    assert not refused("mcp__voice__reply", stopped=True, allowed=frozenset({"mcp__voice__reply"}))


def test_every_tool_runs_without_a_stop() -> None:
    assert not refused("Bash", stopped=False, allowed=frozenset({"mcp__voice__reply"}))


def test_scores_that_do_not_match_the_routes_are_refused() -> None:
    with pytest.raises(ValueError, match="zip"):
        _ = meaning_of([0.9], ROUTES)
