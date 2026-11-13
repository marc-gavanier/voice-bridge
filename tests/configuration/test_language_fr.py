from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language
from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise

type RouteOf = Callable[[Language, str], str]


def test_french_is_spoken_with_a_french_voice() -> None:
    assert language_pack("fr").voice == "fr_female"


def test_french_greets_in_french() -> None:
    assert language_pack("fr").greeting == "Je t'écoute."


def test_french_describes_the_end_of_session_tool_in_french() -> None:
    assert language_pack("fr").end_tool_description.startswith("Dire au revoir")


def test_french_knows_the_subtitle_credit_hallucination() -> None:
    assert "sous-titrage" in language_pack("fr").hallucination_prefixes


def test_french_knows_the_thanks_for_watching_hallucination() -> None:
    pack = language_pack("fr")
    hallucinations = Hallucinations(texts=pack.hallucinations, prefixes=pack.hallucination_prefixes)
    assert is_noise("Merci d'avoir regardé cette vidéo !", hallucinations)


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Stop, est-ce que tu peux arrêter ?", "stop"),
        ("C'est parti.", "yes"),
        ("Lance-toi.", "yes"),
        ("Arrête !", "stop"),
        ("Bon, on laisse ça de côté, arrête de chercher.", "stop"),
        ("Hé, tu peux t'arrêter là ?", "stop"),
        ("Est-ce que tu m'entends ?", "presence"),
        ("Il y a un truc qui coupe.", "problem"),
        ("Tu es...", "unfinished"),
        ("Bon travail.", "thanks"),
        ("Ok, on va mettre fin à la conversation.", "end"),
        ("Là, j'ai redémarré le pont.", "restarted"),
        ("Est-ce que tu peux lire le Wikipédia sur la Savoie ?", "request"),
        ("Et donc, qu'est-ce que c'est la suite ?", "question"),
        ("Non.", "no"),
        ("C'est exactement ça.", "yes"),
    ],
)
def test_french_words_take_the_route_of_their_meaning(
    words: str, expected: str, route_of: Callable[[Language, str], str]
) -> None:
    assert route_of("fr", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Mais sans que ce soit nécessairement stop.",
        "J'ai pas dit stop parce que t'es allé super vite, donc il n'y avait rien à stopper.",
        "Oui, ça s'est bien arrêté.",
        "Est-ce que tu as eu le temps de lire l'article sur la Savoie ou tu t'es arrêté avant ?",
        "Ok on commence par le stop",
        "Allez, c'est parti.",
        "Vas-y, lance.",
    ],
)
def test_french_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("fr", words) != "stop"


def test_french_refuses_tools_in_french() -> None:
    assert "arrêter" in language_pack("fr").stop_refusal


def test_french_asks_the_main_agent_to_delegate_in_french() -> None:
    assert "arrière-plan" in language_pack("fr").delegation_refusal
