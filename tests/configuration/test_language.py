from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from voice_bridge.configuration.language import (
    AcknowledgementRoute,
    language_pack,
    load_instructions,
    parse_language_pack,
)
from voice_bridge.configuration.settings import Language, UnderstandingSettings

LANGUAGES: Final[tuple[Language, ...]] = ("ar", "de", "en", "es", "fr", "hi", "it", "nl", "pt")
ANNOUNCED_AGENTS: Final = 5


type RouteOf = Callable[[Language, str], str]


def test_english_is_transcribed_as_english() -> None:
    assert language_pack("en").whisper_code == "en"


def test_english_greets_in_english() -> None:
    assert language_pack("en").greeting == "I'm listening."


def test_english_describes_the_board_tool_in_english() -> None:
    assert language_pack("en").board_tool_description.startswith("Read the board")


def test_english_describes_the_end_of_session_tool_in_english() -> None:
    assert language_pack("en").end_tool_description.startswith("Say goodbye")


def test_english_asks_the_main_agent_to_delegate_in_english() -> None:
    assert "background agent" in language_pack("en").delegation_refusal


def test_english_instructions_ask_to_hand_work_to_a_background_agent() -> None:
    assert "to a background agent" in language_pack("en").instructions


def test_default_instructions_are_written_in_the_language() -> None:
    assert "in English" in language_pack("en").instructions


def test_instructions_come_from_the_user_file_when_it_exists(tmp_path: Path) -> None:
    path = tmp_path / "instructions.md"
    _ = path.write_text("  Speak like a pirate.\n", encoding="utf-8")
    assert load_instructions(path, default="Be brief.") == "Speak like a pirate."


def test_instructions_fall_back_to_the_default_without_a_user_file(tmp_path: Path) -> None:
    assert load_instructions(tmp_path / "absent.md", default="Be brief.") == "Be brief."


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
def test_english_words_take_the_route_of_their_meaning(
    words: str, expected: str, route_of: Callable[[Language, str], str]
) -> None:
    assert route_of("en", words) == expected


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_route_has_enough_examples(language: Language) -> None:
    assert min(len(route.examples) for route in language_pack(language).acknowledgements) >= 15


@pytest.mark.parametrize("language", LANGUAGES)
def test_only_the_stop_route_stops(language: Language) -> None:
    stopping = {route.name for route in language_pack(language).acknowledgements if route.stops}
    assert stopping == {"stop"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_stop_needs_a_close_match(language: Language) -> None:
    stop = next(route for route in language_pack(language).acknowledgements if route.name == "stop")
    assert stop.threshold is not None
    assert stop.threshold > UnderstandingSettings().threshold


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_route_has_acknowledgements(language: Language) -> None:
    assert all(route.sentences for route in language_pack(language).acknowledgements)


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_acknowledgement_is_one_voxtral_derails_on(language: Language) -> None:
    pack = language_pack(language)
    sentences = {sentence for route in pack.acknowledgements for sentence in route.sentences}
    assert not (sentences | set(pack.neutral_acknowledgements)) & {"Top.", "OK.", "Ok."}


MINIMAL_PACK = """
whisper_code = "en"
voice = "neutral_female"
greeting = "Hello."
stop_refusal = "Stopped."
delegation_refusal = "Delegate."
reply_tool_description = "Speak"
reply_text_description = "Text"
end_tool_description = "End"
end_text_description = "Goodbye"
board_tool_description = "Board"
hallucinations = ["", "you"]
hallucination_prefixes = ["subtitles by"]
neutral_acknowledgements = ["Okay."]

[announcements]
at_work = ["One at work."]
many_at_work = "Many at work."
finished = ["One finished, one left."]
many_left = "One finished, many left."
none_at_work = "None at work."

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


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_announces_up_to_five_agents_at_work(language: Language) -> None:
    assert len(language_pack(language).announcements.at_work) == ANNOUNCED_AGENTS


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_announces_up_to_five_agents_left(language: Language) -> None:
    assert len(language_pack(language).announcements.finished) == ANNOUNCED_AGENTS


def every_announcement(language: Language) -> list[str]:
    announcements = language_pack(language).announcements
    return [
        *announcements.at_work,
        announcements.many_at_work,
        *announcements.finished,
        announcements.many_left,
        announcements.none_at_work,
    ]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_announcement_of_a_language_is_its_own_sentence(language: Language) -> None:
    sentences = every_announcement(language)
    assert len(set(sentences)) == len(sentences)


def test_a_language_file_without_announcements_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('none_at_work = "None at work."', ""), instructions="")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_is_transcribed_in_itself(language: Language) -> None:
    assert language_pack(language).whisper_code == language
