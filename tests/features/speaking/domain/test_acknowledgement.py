import re

from voice_bridge.features.speaking.domain.acknowledgement import fresh, kind_of

PATTERNS = (re.compile(r"\?$"), re.compile(r"^non\b", re.IGNORECASE), re.compile(""))


def test_the_first_pattern_that_matches_gives_the_kind() -> None:
    assert kind_of("Non, pas ça ?", PATTERNS) == 0


def test_a_later_pattern_matches_when_earlier_ones_do_not() -> None:
    assert kind_of("Non, pas besoin.", PATTERNS) == 1


def test_an_empty_pattern_catches_everything_else() -> None:
    assert kind_of("Le dépôt est propre.", PATTERNS) == 2


def test_surrounding_spaces_do_not_hide_the_end_of_a_question() -> None:
    assert kind_of(" On en est où ? ", PATTERNS) == 0


def test_words_no_pattern_matches_have_no_kind() -> None:
    assert kind_of("Le dépôt est propre.", PATTERNS[:2]) is None


def test_the_last_sentence_played_is_left_out() -> None:
    assert fresh(("D'accord.", "Entendu.", "Noté."), "Entendu.") == ("D'accord.", "Noté.")


def test_a_single_sentence_is_played_again() -> None:
    assert fresh(("D'accord.",), "D'accord.") == ("D'accord.",)


def test_every_sentence_is_fresh_before_any_was_played() -> None:
    assert fresh(("D'accord.", "Entendu."), None) == ("D'accord.", "Entendu.")
