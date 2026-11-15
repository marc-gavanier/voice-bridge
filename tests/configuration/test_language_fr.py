from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language
from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise

type RouteOf = Callable[[Language, str], str]


def said(*parts: str) -> str:
    return " ".join(parts)


def test_french_is_spoken_with_a_french_voice() -> None:
    assert language_pack("fr").voice == "fr_female"


def test_french_greets_in_french() -> None:
    assert "Je t'écoute." in language_pack("fr").greetings


def test_french_describes_the_end_of_session_tool_in_french() -> None:
    assert language_pack("fr").end_tool_description.startswith("Dire au revoir")


def test_french_tells_claude_that_the_board_gives_each_agents_latest_action() -> None:
    assert "dernière action" in language_pack("fr").board_tool_description


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
        ("C'est parti.", "go_ahead"),
        ("Lance-toi.", "go_ahead"),
        ("Oui, fais-le.", "go_ahead"),
        ("Oui, c'est bien.", "yes"),
        ("Je garde.", "yes"),
        ("Arrête !", "stop"),
        ("Bon, on laisse ça de côté, arrête de chercher.", "stop"),
        ("Hé, tu peux t'arrêter là ?", "stop"),
        ("Est-ce que tu m'entends ?", "presence"),
        ("Il y a un truc qui coupe.", "problem"),
        ("Tu es...", "unfinished"),
        ("Bon travail.", "compliment"),
        ("Bravo, tu as bien travaillé.", "compliment"),
        ("Super boulot.", "compliment"),
        ("Merci beaucoup.", "thanks"),
        ("Ok, on va mettre fin à la conversation.", "end"),
        ("Là, j'ai redémarré le pont.", "presence"),
        ("Ça y est, j'ai redémarré.", "presence"),
        ("Tu m'entends ?", "presence"),
        ("J'ai une idée…", "idea_coming"),
        ("Je pensais à un truc.", "idea_coming"),
        ("On pourrait utiliser un autre outil.", "idea"),
        ("On s'arrête là.", "end"),
        ("On s'arrête là pour le moment.", "end"),
        ("Merci pour le coup de main.", "thanks"),
        ("Tu as fait du bon boulot.", "compliment"),
        ("Il me vient une idée.", "idea_coming"),
        ("Vas-y, tu peux lancer.", "go_ahead"),
        ("Oui, ça me convient.", "yes"),
        ("Est-ce que tu peux lire le Wikipédia sur la Savoie ?", "request"),
        ("Et donc, qu'est-ce que c'est la suite ?", "question"),
        ("Non.", "no"),
        ("C'est exactement ça.", "yes"),
        ("On peut lancer ça maintenant.", "go_ahead"),
        (
            "Oui, c'est plus clair. Si c'est faisable dans un temps raisonnable, on peut lancer ça maintenant.",
            "go_ahead",
        ),
        (
            said(
                "Ouais ça me va, prépare ça maintenant et on verra ça demain quand je cours, quand j'irai courir.",
                "Mais tu peux déjà préparer ça maintenant et on l'activera quand on redémarrera le pont.",
            ),
            "go_ahead",
        ),
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
        "On laisse comme ça.",
        "On laisse.",
        "On s'arrête là.",
        "Non, on laisse ça comme ça.",
    ],
)
def test_french_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("fr", words) != "stop"


@pytest.mark.parametrize(
    "words",
    [
        said(
            "C'est dommage que dans les moments longs comme ça,",
            "tu ne puisses pas me dire ce qui est en train de se passer.",
        ),
        said(
            "Tu ne m'as peut-être pas entendu parce qu'il y a eu encore un problème avec Mumble.",
            "Mais je voulais dire que j'ai validé dans mes notes les réponses de validation.",
        ),
        "Est-ce que les voix sont synthétisées plus rapidement qu'elles ne prennent de temps à prononcer ?",
        said(
            "Sur le ticket de 44 qui parlait de la fluidification de la parole,",
            "il resterait quoi à faire qu'on n'a pas encore abordé ?",
        ),
        said(
            "Non, je cherche vraiment à accélérer, fluidifier la conversation. Tu m'as parlé des 1,2 secondes.",
            "Je veux en savoir plus sur pourquoi on a mis ça en place, à quoi ça sert.",
        ),
        said(
            "Ah oui, je voulais te dire que dans mes notes aussi,",
            "j'ai relu valider, trier, filtrer, ajouter les éléments du...",
        ),
        "Est-ce que tu peux regarder ce qui reste à faire sur 10-44 ?",
    ],
)
def test_french_words_close_to_no_route_get_the_neutral_acknowledgement(words: str, route_of: RouteOf) -> None:
    assert route_of("fr", words) == "neutral"


def test_french_refuses_tools_in_french() -> None:
    assert "arrêter" in language_pack("fr").stop_refusal


def test_french_asks_the_main_agent_to_delegate_in_french() -> None:
    assert "arrière-plan" in language_pack("fr").delegation_refusal


def test_french_announces_two_tasks_in_progress_in_french() -> None:
    assert language_pack("fr").announcements.at_work[0] == "Deux tâches en cours."


def test_french_announces_more_than_five_tasks_in_progress_in_french() -> None:
    assert language_pack("fr").announcements.many_at_work == "Plus de cinq tâches en cours."


def test_french_describes_the_board_tool_in_french() -> None:
    assert language_pack("fr").board_tool_description.startswith("Lire le tableau des agents")


def test_french_describes_the_play_tool_in_french() -> None:
    assert language_pack("fr").play_tool_description.startswith("Faire écouter un fichier audio")
