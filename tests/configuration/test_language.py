from pathlib import Path

import pytest
from pydantic import ValidationError

from voice_bridge.configuration.language import (
    AcknowledgementRoute,
    language_pack,
    load_instructions,
    parse_language_pack,
)
from voice_bridge.configuration.settings import Language, UnderstandingSettings
from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise
from voice_bridge.features.understanding.abilities.understand import Understanding
from voice_bridge.features.understanding.domain.meaning import Route
from voice_bridge.features.understanding.implementations.embeddings import Encoder, load_encoder, router


def test_english_is_transcribed_as_english() -> None:
    assert language_pack("en").whisper_code == "en"


def test_french_is_spoken_with_a_french_voice() -> None:
    assert language_pack("fr").voice == "fr_female"


def test_english_greets_in_english() -> None:
    assert language_pack("en").greeting == "I'm listening."


def test_french_greets_in_french() -> None:
    assert language_pack("fr").greeting == "Je t'écoute."


def test_english_describes_the_end_of_session_tool_in_english() -> None:
    assert language_pack("en").end_tool_description.startswith("Say goodbye")


def test_french_describes_the_end_of_session_tool_in_french() -> None:
    assert language_pack("fr").end_tool_description.startswith("Dire au revoir")


def test_french_knows_the_subtitle_credit_hallucination() -> None:
    assert "sous-titrage" in language_pack("fr").hallucination_prefixes


def test_french_knows_the_thanks_for_watching_hallucination() -> None:
    pack = language_pack("fr")
    hallucinations = Hallucinations(texts=pack.hallucinations, prefixes=pack.hallucination_prefixes)
    assert is_noise("Merci d'avoir regardé cette vidéo !", hallucinations)


def test_default_instructions_are_written_in_the_language() -> None:
    assert "in English" in language_pack("en").instructions


def test_instructions_come_from_the_user_file_when_it_exists(tmp_path: Path) -> None:
    path = tmp_path / "instructions.md"
    _ = path.write_text("  Speak like a pirate.\n", encoding="utf-8")
    assert load_instructions(path, default="Be brief.") == "Speak like a pirate."


def test_instructions_fall_back_to_the_default_without_a_user_file(tmp_path: Path) -> None:
    assert load_instructions(tmp_path / "absent.md", default="Be brief.") == "Be brief."


@pytest.fixture(scope="module")
def encoder() -> Encoder:
    return load_encoder()


def route_of(language: Language, words: str, encoder: Encoder) -> str:
    pack = language_pack(language)
    routes = tuple(
        Route(name=route.name, threshold=route.threshold or 0.5, stops=route.stops) for route in pack.acknowledgements
    )
    scores = router(encoder, [route.examples for route in pack.acknowledgements])
    meaning = Understanding(scores=scores, routes=routes)(words)
    return "neutral" if meaning.route is None else routes[meaning.route].name


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
def test_french_words_take_the_route_of_their_meaning(words: str, expected: str, encoder: Encoder) -> None:
    assert route_of("fr", words, encoder) == expected


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
def test_french_words_about_stopping_do_not_stop(words: str, encoder: Encoder) -> None:
    assert route_of("fr", words, encoder) != "stop"


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Stop, can you stop?", "stop"),
        ("Can you hear me?", "presence"),
        ("Could you check the logs?", "request"),
        ("There is a glitch.", "problem"),
        ("Thanks.", "thanks"),
        ("Goodbye.", "end"),
    ],
)
def test_english_words_take_the_route_of_their_meaning(words: str, expected: str, encoder: Encoder) -> None:
    assert route_of("en", words, encoder) == expected


@pytest.mark.parametrize("language", ["en", "fr"])
def test_every_route_has_enough_examples(language: Language) -> None:
    assert min(len(route.examples) for route in language_pack(language).acknowledgements) >= 15


@pytest.mark.parametrize("language", ["en", "fr"])
def test_only_the_stop_route_stops(language: Language) -> None:
    stopping = {route.name for route in language_pack(language).acknowledgements if route.stops}
    assert stopping == {"stop"}


@pytest.mark.parametrize("language", ["en", "fr"])
def test_a_stop_needs_a_close_match(language: Language) -> None:
    stop = next(route for route in language_pack(language).acknowledgements if route.name == "stop")
    assert stop.threshold is not None
    assert stop.threshold > UnderstandingSettings().threshold


@pytest.mark.parametrize("language", ["en", "fr"])
def test_every_route_has_acknowledgements(language: Language) -> None:
    assert all(route.sentences for route in language_pack(language).acknowledgements)


@pytest.mark.parametrize("language", ["en", "fr"])
def test_no_acknowledgement_is_one_voxtral_derails_on(language: Language) -> None:
    pack = language_pack(language)
    sentences = {sentence for route in pack.acknowledgements for sentence in route.sentences}
    assert not (sentences | set(pack.neutral_acknowledgements)) & {"Top.", "OK.", "Ok."}


def test_french_refuses_tools_in_french() -> None:
    assert "arrêter" in language_pack("fr").stop_refusal


MINIMAL_PACK = """
whisper_code = "en"
voice = "neutral_female"
greeting = "Hello."
stop_refusal = "Stopped."
reply_tool_description = "Speak"
reply_text_description = "Text"
reply_working_description = "Working"
end_tool_description = "End"
end_text_description = "Goodbye"
hallucinations = ["", "you"]
hallucination_prefixes = ["subtitles by"]
neutral_acknowledgements = ["Okay."]

[[acknowledgements]]
name = "yes"
examples = ["Yes."]
sentences = ["Good."]
"""


def test_a_language_file_gives_its_pack_with_the_instructions() -> None:
    assert parse_language_pack(MINIMAL_PACK, instructions="Be brief.").instructions == "Be brief."


def test_a_route_of_a_language_file_needs_no_threshold_and_does_not_stop() -> None:
    route = parse_language_pack(MINIMAL_PACK, instructions="").acknowledgements[0]
    assert route == AcknowledgementRoute(name="yes", examples=("Yes.",), sentences=("Good.",))


def test_the_hallucinations_of_a_language_file_are_a_set() -> None:
    assert parse_language_pack(MINIMAL_PACK, instructions="").hallucinations == frozenset({"", "you"})


def test_a_language_file_with_an_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(
            MINIMAL_PACK.replace('greeting = "Hello."', 'greeting = "Hello."\ngreting = "Hi."'), instructions=""
        )


def test_a_language_file_missing_a_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('greeting = "Hello."', ""), instructions="")


def test_a_route_with_an_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('name = "yes"', 'name = "yes"\nstop = true'), instructions="")
