from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_spanish_is_spoken_with_a_spanish_voice() -> None:
    assert language_pack("es").voice == "es_female"


def test_spanish_greets_in_spanish() -> None:
    assert language_pack("es").greeting == "Te escucho."


def test_spanish_knows_the_subtitle_credit_hallucination() -> None:
    assert "subtítulos realizados por" in language_pack("es").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Para, ¿puedes parar ya?", "stop"),
        ("¿Me oyes bien?", "presence"),
        ("Muchas gracias, ha quedado genial.", "thanks"),
        ("Hasta mañana, buenas noches.", "end"),
        ("¿Puedes ejecutar las pruebas?", "request"),
        ("Sí, hagámoslo así.", "yes"),
    ],
)
def test_spanish_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("es", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "¿Has visto si se ha parado bien?",
        "Venga, empezamos.",
    ],
)
def test_spanish_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("es", words) != "stop"
