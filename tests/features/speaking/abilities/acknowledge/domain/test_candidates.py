import pytest

from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import (
    NEUTRAL,
    NEUTRAL_QUESTION,
    Candidates,
    candidates,
    fallback,
    pool_of,
)

POOLS = (("Let me see.", "Good question."), (), ("Alright.", "Fine."))


def test_there_is_no_candidate_before_any_pool_is_recorded() -> None:
    assert candidates((), 0, None) is None


def test_the_kind_of_the_words_chooses_the_pool() -> None:
    assert candidates(POOLS, 0, None) == Candidates(pool=0, sentences=("Let me see.", "Good question."))


def test_words_of_no_kind_get_the_last_pool() -> None:
    assert candidates(POOLS, None, None) == Candidates(pool=2, sentences=("Alright.", "Fine."))


def test_an_empty_pool_has_no_candidate() -> None:
    assert candidates(POOLS, 1, None) is None


def test_the_last_sentence_played_is_not_a_candidate() -> None:
    assert candidates(POOLS, 0, "Let me see.") == Candidates(pool=0, sentences=("Good question.",))


def test_the_last_sentence_played_from_another_pool_is_not_a_candidate_either() -> None:
    assert candidates(POOLS, 0, "Good question.") == Candidates(pool=0, sentences=("Let me see.",))


def test_words_of_a_route_get_the_pool_of_that_route() -> None:
    assert pool_of(2, "Where are we?", routes=3) == 2


def test_words_of_no_route_get_the_neutral_pool() -> None:
    assert pool_of(None, "The repository is clean.", routes=3) == 3


def test_a_question_of_no_route_gets_the_neutral_question_pool() -> None:
    assert pool_of(None, "Are the new thresholds on?", routes=3) == 4


@pytest.mark.parametrize("words", ["هل انتهيت؟", "終わった\N{FULLWIDTH QUESTION MARK}", "Where are we ?  "])
def test_a_question_in_any_script_gets_the_neutral_question_pool(words: str) -> None:
    assert pool_of(None, words, routes=3) == 4


def test_a_question_mark_inside_the_words_does_not_make_a_question() -> None:
    assert pool_of(None, "Why? Because it works.", routes=3) == 3


def test_empty_words_get_the_neutral_pool() -> None:
    assert pool_of(None, "", routes=3) == 3


def test_a_statement_falls_back_on_the_neutral_pool() -> None:
    assert fallback("The repository is clean.") == NEUTRAL


def test_a_question_falls_back_on_the_neutral_question_pool() -> None:
    assert fallback("Are the new thresholds on?") == NEUTRAL_QUESTION
