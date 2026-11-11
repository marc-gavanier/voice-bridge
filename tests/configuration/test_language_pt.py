from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_portuguese_is_spoken_with_a_portuguese_voice() -> None:
    assert language_pack("pt").voice == "pt_female"


def test_portuguese_greets_in_portuguese() -> None:
    assert language_pack("pt").greeting == "Estou ouvindo."


def test_portuguese_knows_the_subtitle_credit_hallucination() -> None:
    assert "legendas pela comunidade" in language_pack("pt").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Pare, você pode parar agora?", "stop"),
        ("Você está me ouvindo bem?", "presence"),
        ("Muito obrigado, ficou ótimo.", "thanks"),
        ("Até amanhã, boa noite.", "end"),
        ("Você pode rodar os testes?", "request"),
        ("Sim, vamos fazer assim.", "yes"),
    ],
)
def test_portuguese_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("pt", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Você viu se parou direito?",
        "Vamos começar.",
    ],
)
def test_portuguese_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("pt", words) != "stop"
