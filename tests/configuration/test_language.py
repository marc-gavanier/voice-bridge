import re
from pathlib import Path

import pytest

from voice_bridge.configuration.language import language_pack, load_instructions
from voice_bridge.configuration.settings import Language


def test_english_is_transcribed_as_english() -> None:
    assert language_pack("en").whisper_code == "en"


def test_french_is_spoken_with_a_french_voice() -> None:
    assert language_pack("fr").voice == "fr_female"


def test_english_greets_in_english() -> None:
    assert language_pack("en").greeting == "I'm listening."


def test_french_greets_in_french() -> None:
    assert language_pack("fr").greeting == "Je t'écoute."


def test_french_knows_the_subtitle_credit_hallucination() -> None:
    assert "sous-titrage" in language_pack("fr").hallucination_prefixes


def test_default_instructions_are_written_in_the_language() -> None:
    assert "in English" in language_pack("en").instructions


def test_instructions_come_from_the_user_file_when_it_exists(tmp_path: Path) -> None:
    path = tmp_path / "instructions.md"
    _ = path.write_text("  Speak like a pirate.\n", encoding="utf-8")
    assert load_instructions(path, default="Be brief.") == "Speak like a pirate."


def test_instructions_fall_back_to_the_default_without_a_user_file(tmp_path: Path) -> None:
    assert load_instructions(tmp_path / "absent.md", default="Be brief.") == "Be brief."


def kind(language: Language, words: str) -> tuple[str, ...]:
    rules = language_pack(language).acknowledgements
    return next(sentences for pattern, sentences in rules if re.search(pattern, words.strip(), re.IGNORECASE))


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Est-ce que tu m'entends ?", "Je t'entends."),
        ("Est-ce que tu peux regarder les journaux ?", "Je regarde."),
        ("Pourquoi ça coupe ?", "Je vérifie."),
        ("Là, il y a une coupure.", "Ah, je regarde ça."),
        ("Oui, j'aimerais bien...", "Je t'écoute."),
        ("Donc,", "Je t'écoute."),
        ("Bon travail.", "Merci !"),
        ("Ok, on va mettre fin à la conversation.", "À plus tard."),
        ("Là, j'ai redémarré le pont.", "Bien reçu."),
        ("Comment on fait ?", "Voyons."),
        ("Je me demande si on pourrait faire une règle.", "Intéressant."),
        ("Non, pas besoin.", "Compris."),
        ("Ouais, vas-y.", "Parfait."),
        ("Je suis dehors.", "D'accord."),
    ],
)
def test_french_acknowledges_after_what_was_said(words: str, expected: str) -> None:
    assert expected in kind("fr", words)


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("Can you hear me?", "I can hear you."),
        ("Could you check the logs?", "On it."),
        ("Why is it so slow?", "Let's see."),
        ("There is a glitch.", "I'll check."),
        ("So...", "Go on."),
        ("Thanks.", "Thanks!"),
        ("Yeah, go ahead.", "Perfect."),
        ("No need.", "Understood."),
        ("I'm outside.", "Okay."),
    ],
)
def test_english_acknowledges_after_what_was_said(words: str, expected: str) -> None:
    assert expected in kind("en", words)


@pytest.mark.parametrize("language", ["en", "fr"])
def test_anything_gets_an_acknowledgement(language: Language) -> None:
    assert kind(language, "Zzz")


@pytest.mark.parametrize("language", ["en", "fr"])
def test_no_acknowledgement_is_one_voxtral_derails_on(language: Language) -> None:
    sentences = {sentence for _, pool in language_pack(language).acknowledgements for sentence in pool}
    assert not sentences & {"Top.", "OK.", "Ok."}
