from pathlib import Path

from voice_bridge.configuration.language import language_pack, load_instructions


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


def test_french_acknowledges_a_question_by_looking_into_it() -> None:
    assert "Je regarde." in language_pack("fr").question_acknowledgements


def test_french_acknowledges_a_statement_without_promising_to_look() -> None:
    assert "Je regarde." not in language_pack("fr").statement_acknowledgements
