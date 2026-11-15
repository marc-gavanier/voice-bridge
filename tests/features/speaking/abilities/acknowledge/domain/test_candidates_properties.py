from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import (
    NEUTRAL,
    NEUTRAL_QUESTION,
    QUESTION_MARKS,
    fallback,
    pool_of,
)

ROUTES = st.integers(min_value=0, max_value=20)
SPACES = st.text(alphabet=" \t\n")


def joined(words: str, mark: str, spaces: str) -> str:
    return words + mark + spaces


def asks_nothing(words: str) -> bool:
    return words.rstrip()[-1:] not in QUESTION_MARKS


QUESTIONS = st.builds(joined, st.text(), st.sampled_from(sorted(QUESTION_MARKS)), SPACES)
STATEMENTS = st.text().filter(asks_nothing)


@given(QUESTIONS, ROUTES)
def test_a_question_of_no_route_always_gets_the_neutral_question_pool(words: str, routes: int) -> None:
    assert pool_of(None, words, routes=routes) == routes + 1


@given(STATEMENTS, ROUTES)
def test_words_of_no_route_that_ask_nothing_always_get_the_neutral_pool(words: str, routes: int) -> None:
    assert pool_of(None, words, routes=routes) == routes


@given(st.text(), ROUTES, ROUTES)
def test_words_of_a_route_always_get_its_pool(words: str, route: int, more: int) -> None:
    assert pool_of(route, words, routes=route + more + 1) == route


@given(QUESTIONS)
def test_a_question_always_falls_back_on_the_neutral_question_pool(words: str) -> None:
    assert fallback(words) == NEUTRAL_QUESTION


@given(STATEMENTS)
def test_words_that_ask_nothing_always_fall_back_on_the_neutral_pool(words: str) -> None:
    assert fallback(words) == NEUTRAL
