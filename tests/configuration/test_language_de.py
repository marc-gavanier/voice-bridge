from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_german_is_spoken_with_a_german_voice() -> None:
    assert language_pack("de").voice == "de_female"


def test_german_greets_in_german() -> None:
    assert language_pack("de").greeting == "Ich höre zu."


def test_german_knows_the_subtitle_credit_hallucination() -> None:
    assert "untertitel im auftrag" in language_pack("de").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Stopp, kannst du bitte sofort aufhören?", "stop"),
        ("Hörst du mich überhaupt?", "presence"),
        ("Vielen Dank, das war super.", "thanks"),
        ("Bis morgen, gute Nacht.", "end"),
        ("Kannst du die Tests laufen lassen?", "request"),
        ("Ja, genau so machen wir das.", "yes"),
    ],
)
def test_german_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("de", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Hast du gesehen, ob es richtig gestoppt hat?",
        "Los, wir fangen an.",
    ],
)
def test_german_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("de", words) != "stop"
