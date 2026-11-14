from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_portuguese_is_spoken_with_a_portuguese_voice() -> None:
    assert language_pack("pt").voice == "pt_female"


def test_portuguese_greets_in_portuguese() -> None:
    assert "Estou ouvindo." in language_pack("pt").greetings


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
        ("Sim, vamos fazer assim.", "go_ahead"),
        ("Você fez um trabalho muito bom.", "compliment"),
        ("Sim, assim está bom.", "yes"),
        ("Sim, faz isso.", "go_ahead"),
        ("Acabei de ter uma ideia…", "idea_coming"),
        ("Muito obrigado por isso.", "thanks"),
        ("Reiniciei o aplicativo.", "presence"),
        ("Paramos por aqui hoje.", "end"),
        ("Você fez um ótimo trabalho, sério.", "compliment"),
        ("Obrigado pela ajuda.", "thanks"),
        ("Vai, pode mandar.", "go_ahead"),
        ("Sim, assim me serve.", "yes"),
        ("Espera, acabou de me ocorrer uma coisa.", "idea_coming"),
        ("A gente podia usar outra ferramenta.", "idea"),
        ("Pronto, já reiniciei.", "presence"),
        ("Paramos por aqui por enquanto.", "end"),
        ("Bom, deixa pra lá, para de procurar.", "stop"),
        ("Ei, você pode parar aí?", "stop"),
        ("Para!", "stop"),
        ("Não.", "no"),
        ("E aí, qual é o próximo passo?", "question"),
    ],
)
def test_portuguese_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("pt", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Você viu se parou direito?",
        "Vamos começar.",
        "Deixa como está.",
        "Eu não disse para, você que foi rápido demais.",
        "Sim, parou direitinho.",
        "Você teve tempo de ler o artigo ou parou antes de terminar?",
        "Certo, vamos começar pela parada.",
        "Deixa assim.",
        "Deixa como está, tá bom.",
        "Paramos por aqui.",
        "Não, deixa como está.",
    ],
)
def test_portuguese_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("pt", words) != "stop"
