from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_dutch_is_spoken_with_a_dutch_voice() -> None:
    assert language_pack("nl").voice == "nl_female"


def test_dutch_greets_in_dutch() -> None:
    assert "Ik luister." in language_pack("nl").greetings


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
        ("Ja, zo doen we het.", "go_ahead"),
        ("Je hebt echt goed werk geleverd.", "compliment"),
        ("Ja, zo is het goed.", "yes"),
        ("Ja, doe het.", "go_ahead"),
        ("Ik kreeg net een idee…", "idea_coming"),
        ("Heel erg bedankt daarvoor.", "thanks"),
        ("Ik heb de app opnieuw gestart.", "presence"),
        ("We stoppen hier voor vandaag.", "end"),
        ("Bedankt voor de hulp.", "thanks"),
        ("Toe maar, je kunt het starten.", "go_ahead"),
        ("Ja, zo vind ik het goed.", "yes"),
        ("Wacht, ik bedenk net iets.", "idea_coming"),
        ("We zouden een ander hulpmiddel kunnen gebruiken.", "idea"),
        ("Zo, ik heb opnieuw opgestart.", "presence"),
        ("We stoppen hier voorlopig.", "end"),
        ("Laat maar zitten, hou op met zoeken.", "stop"),
        ("Hé, kun je daar stoppen?", "stop"),
        ("Hou op!", "stop"),
        ("Nee.", "no"),
        ("Dus, wat is de volgende stap?", "question"),
    ],
)
def test_dutch_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("nl", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "Heb je gezien of het goed gestopt is?",
        "Kom, we beginnen.",
        "We laten het zo.",
        "Ik zei geen stop, je ging gewoon te snel.",
        "Ja, het is netjes gestopt.",
        "Had je tijd om het artikel uit te lezen of ben je eerder gestopt?",
        "Oké, we beginnen met het stoppen.",
        "Laat het zo, het is goed.",
        "We stoppen hier.",
        "Nee, we laten het zo.",
    ],
)
def test_dutch_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("nl", words) != "stop"
