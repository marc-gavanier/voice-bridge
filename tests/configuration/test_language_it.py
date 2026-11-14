from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_italian_is_spoken_with_a_italian_voice() -> None:
    assert language_pack("it").voice == "it_female"


def test_italian_greets_in_italian() -> None:
    assert "Ti ascolto." in language_pack("it").greetings


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
        ("Sì, facciamo così.", "go_ahead"),
        ("Hai fatto un ottimo lavoro.", "compliment"),
        ("Sì, va bene così.", "yes"),
        ("Sì, fallo.", "go_ahead"),
        ("Mi è appena venuta un'idea…", "idea_coming"),
        ("Grazie mille per questo.", "thanks"),
        ("Ho riavviato l'app.", "presence"),
        ("Ci fermiamo qui per oggi.", "end"),
        ("Hai fatto davvero un bel lavoro.", "compliment"),
        ("Grazie per l'aiuto.", "thanks"),
        ("Vai, puoi lanciarlo.", "go_ahead"),
        ("Sì, così mi va bene.", "yes"),
        ("Aspetta, mi è appena venuta in mente una cosa.", "idea_coming"),
        ("Potremmo usare un altro strumento.", "idea"),
        ("Ecco, ho riavviato.", "presence"),
        ("Ci fermiamo qui per adesso.", "end"),
        ("Dai, lascia perdere, smetti di cercare.", "stop"),
        ("Ehi, puoi fermarti lì?", "stop"),
        ("Fermati!", "stop"),
        ("No.", "no"),
        ("Allora, qual è il prossimo passo?", "question"),
    ],
)
def test_italian_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("it", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Hai visto se si è fermato bene?",
        "Dai, cominciamo.",
        "Lasciamo così.",
        "Non ho detto stop, sei andato troppo veloce.",
        "Sì, si è fermato bene.",
        "Hai avuto tempo di leggere l'articolo o ti sei fermato prima di finire?",
        "Va bene, cominciamo dallo stop.",
        "Lascialo così, va bene.",
        "Ci fermiamo qui.",
        "No, lasciamo così.",
    ],
)
def test_italian_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("it", words) != "stop"
