from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_dutch_is_spoken_with_a_dutch_voice() -> None:
    assert language_pack("nl").voice == "nl_female"


def test_dutch_greets_in_dutch() -> None:
    assert language_pack("nl").greeting == "Ik luister."


def test_dutch_knows_the_subtitle_credit_hallucination() -> None:
    assert "ondertiteld door" in language_pack("nl").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Stop, kun je meteen ophouden?", "stop"),
        ("Hoor je me goed?", "presence"),
        ("Heel erg bedankt, het is mooi geworden.", "thanks"),
        ("Tot morgen, welterusten.", "end"),
        ("Kun je de tests draaien?", "request"),
        ("Ja, zo doen we het.", "yes"),
    ],
)
def test_dutch_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("nl", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Heb je gezien of het goed gestopt is?",
        "Kom, we beginnen.",
    ],
)
def test_dutch_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("nl", words) != "stop"
