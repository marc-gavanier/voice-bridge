from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_spanish_is_spoken_with_a_spanish_voice() -> None:
    assert language_pack("es").voice == "es_female"


def test_spanish_greets_in_spanish() -> None:
    assert "Te escucho." in language_pack("es").greetings


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
        ("Sí, hagámoslo así.", "go_ahead"),
        ("Has hecho un trabajo muy bueno.", "compliment"),
        ("Sí, así está bien.", "yes"),
        ("Sí, hazlo.", "go_ahead"),
        ("Se me acaba de ocurrir una idea…", "idea_coming"),
        ("Muchas gracias por eso.", "thanks"),
        ("He reiniciado la aplicación.", "presence"),
        ("Lo dejamos aquí por hoy.", "end"),
        ("Has hecho un buen trabajo, de verdad.", "compliment"),
        ("Gracias por la ayuda.", "thanks"),
        ("Venga, puedes lanzarlo.", "go_ahead"),
        ("Vamos allá.", "go_ahead"),
        ("Sí, así me vale.", "yes"),
        ("Espera, se me acaba de ocurrir algo.", "idea_coming"),
        ("Vale, ya está reiniciado.", "presence"),
        ("Lo dejamos aquí de momento.", "end"),
        ("Lo dejamos aquí.", "end"),
        ("Bueno, déjalo, deja de buscar.", "stop"),
        ("Oye, ¿puedes parar ahí?", "stop"),
        ("¡Para!", "stop"),
        ("No.", "no"),
        ("¿Y entonces, qué es lo siguiente?", "question"),
        ("¿Puedes leer la Wikipedia sobre Saboya?", "request"),
    ],
)
def test_spanish_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("es", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "¿Has visto si se ha parado bien?",
        "Venga, empezamos.",
        "Lo dejamos así.",
        "Yo no he dicho para, es que has ido muy rápido.",
        "Sí, se ha parado bien.",
        "¿Has tenido tiempo de leer el artículo o te paraste antes?",
        "Vale, empezamos por la parada.",
        "Déjalo así, ya está bien.",
        "Lo dejamos aquí.",
        "No, lo dejamos así.",
    ],
)
def test_spanish_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("es", words) != "stop"
