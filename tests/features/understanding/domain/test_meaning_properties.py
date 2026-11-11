from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.understanding.domain.meaning import Route, meaning_of

UNIT = st.floats(min_value=-1.0, max_value=1.0)
SCORED_ROUTES = st.lists(st.tuples(UNIT, UNIT, st.booleans()), max_size=8)


def routes_of(scored: list[tuple[float, float, bool]]) -> tuple[Route, ...]:
    return tuple(
        Route(name=str(index), threshold=threshold, stops=stops) for index, (_, threshold, stops) in enumerate(scored)
    )


def scores_of(scored: list[tuple[float, float, bool]]) -> tuple[float, ...]:
    return tuple(score for score, _, _ in scored)


def passing(scored: list[tuple[float, float, bool]]) -> list[float]:
    return [score for score, threshold, _ in scored if score >= threshold]


@given(SCORED_ROUTES)
def test_a_chosen_route_always_reaches_its_threshold(scored: list[tuple[float, float, bool]]) -> None:
    meaning = meaning_of(scores_of(scored), routes_of(scored))
    assert meaning.route is None or scored[meaning.route][0] >= scored[meaning.route][1]


@given(SCORED_ROUTES)
def test_the_chosen_score_is_the_best_that_passes(scored: list[tuple[float, float, bool]]) -> None:
    meaning = meaning_of(scores_of(scored), routes_of(scored))
    assert meaning.route is None or meaning.score == max(passing(scored))


@given(SCORED_ROUTES)
def test_no_route_is_chosen_only_when_none_passes(scored: list[tuple[float, float, bool]]) -> None:
    assert (meaning_of(scores_of(scored), routes_of(scored)).route is None) == (not passing(scored))


@given(SCORED_ROUTES)
def test_only_a_stopping_route_stops(scored: list[tuple[float, float, bool]]) -> None:
    meaning = meaning_of(scores_of(scored), routes_of(scored))
    assert not meaning.stops or scored[meaning.route or 0][2]
