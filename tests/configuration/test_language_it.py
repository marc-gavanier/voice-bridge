from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_italian_is_spoken_with_a_italian_voice() -> None:
    assert language_pack("it").voice == "it_female"


def test_italian_greets_in_italian() -> None:
    assert language_pack("it").greeting == "Ti ascolto."


def test_italian_knows_the_subtitle_credit_hallucination() -> None:
    assert "sottotitoli creati dalla comunità" in language_pack("it").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Fermati, puoi smettere subito?", "stop"),
        ("Mi senti bene adesso?", "presence"),
        ("Grazie mille, è venuto benissimo.", "thanks"),
        ("A domani, buonanotte.", "end"),
        ("Puoi lanciare i test?", "request"),
        ("Sì, facciamo così.", "yes"),
    ],
)
def test_italian_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("it", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Hai visto se si è fermato bene?",
        "Dai, cominciamo.",
    ],
)
def test_italian_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("it", words) != "stop"
