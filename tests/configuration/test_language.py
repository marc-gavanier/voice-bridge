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
ANNOUNCED_COUNTS: Final = 4


type RouteOf = Callable[[Language, str], str]


def test_english_is_transcribed_as_english() -> None:
    assert language_pack("en").whisper_code == "en"


def test_english_greets_in_english() -> None:
    assert "I'm listening." in language_pack("en").greetings


def test_english_describes_the_board_tool_in_english() -> None:
    assert language_pack("en").board_tool_description.startswith("Read the board")


def test_english_describes_the_play_tool_in_english() -> None:
    assert language_pack("en").play_tool_description.startswith("Play an audio file")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_tells_claude_where_clips_must_be(language: Language) -> None:
    assert "{directory}" in language_pack(language).play_path_description


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_tells_claude_to_play_audio_files_with_the_play_tool(language: Language) -> None:
    assert " play " in language_pack(language).instructions


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
        ("You did a really good job.", "compliment"),
        ("Yes, that's fine as it is.", "yes"),
        ("Yes, go on, do it.", "go_ahead"),
        ("I just had an idea…", "idea_coming"),
        ("Thank you so much for that.", "thanks"),
        ("I restarted the app.", "presence"),
        ("Let's stop here for today.", "end"),
        ("Nice work, really.", "compliment"),
        ("Great job, thanks.", "compliment"),
        ("Thanks for the help.", "thanks"),
        ("Go ahead, you can launch it.", "go_ahead"),
        ("Off you go.", "go_ahead"),
        ("Yes, that suits me.", "yes"),
        ("Exactly.", "yes"),
        ("Hang on, something just came to me.", "idea_coming"),
        ("We could try another tool.", "idea"),
        ("Okay, it's restarted.", "presence"),
        ("Let's stop here for now.", "end"),
        ("Let's stop here.", "end"),
        ("Hey, can you stop there?", "stop"),
        ("Okay, leave it, stop searching.", "stop"),
        ("No.", "no"),
        ("So, what's next?", "question"),
    ],
)
def test_english_words_take_the_route_of_their_meaning(
    words: str, expected: str, route_of: Callable[[Language, str], str]
) -> None:
    assert route_of("en", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "I didn't say stop, you went too fast.",
        "Yes, it stopped properly.",
        "Did you have time to read the article or did you stop before?",
        "Okay, let's start with the stop.",
        "Let's leave it like that.",
        "Let's leave it.",
        "Let's stop here.",
        "No, let's leave it as it is.",
    ],
)
def test_english_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("en", words) != "stop"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_route_has_enough_examples(language: Language) -> None:
    assert min(len(route.examples) for route in language_pack(language).acknowledgements) >= 15


def route_names(language: Language) -> list[str]:
    return [route.name for route in language_pack(language).acknowledgements]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_has_the_routes_of_french(language: Language) -> None:
    assert route_names(language) == route_names("fr")


@pytest.mark.parametrize("language", LANGUAGES)
def test_only_the_stop_route_stops(language: Language) -> None:
    stopping = {route.name for route in language_pack(language).acknowledgements if route.stops}
    assert stopping == {"stop"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_only_the_presence_route_greets(language: Language) -> None:
    greeting = {route.name for route in language_pack(language).acknowledgements if route.greets}
    assert greeting == {"presence"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_only_presence_thanks_and_compliments_are_answered_by_their_acknowledgement(language: Language) -> None:
    answered = {route.name for route in language_pack(language).acknowledgements if route.answers}
    assert answered == {"presence", "thanks", "compliment"}


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
stop_refusal = "Stopped."
delegation_refusal = "Delegate."
reply_tool_description = "Speak"
reply_text_description = "Text"
end_tool_description = "End"
end_text_description = "Goodbye"
board_tool_description = "Board"
play_tool_description = "Play"
play_path_description = "Path in {directory}"
play_label_description = "Label"
hallucinations = ["", "you"]
hallucination_prefixes = ["subtitles by"]
neutral_acknowledgements = ["Okay."]

[announcements]
at_work = ["Two at work."]
many_at_work = "Many at work."

[[acknowledgements]]
name = "yes"
examples = ["Yes."]
sentences = ["Good."]

[[acknowledgements]]
name = "presence"
greets = true
examples = ["Are you there?"]
sentences = ["I'm here.", "I hear you."]
"""


def test_a_language_file_gives_its_pack_with_the_instructions() -> None:
    assert parse_language_pack(MINIMAL_PACK, instructions="Be brief.").instructions == "Be brief."


def test_a_route_of_a_language_file_needs_no_threshold_and_neither_stops_nor_greets_nor_answers() -> None:
    route = parse_language_pack(MINIMAL_PACK, instructions="").acknowledgements[0]
    assert route == AcknowledgementRoute(name="yes", examples=("Yes.",), sentences=("Good.",))


def test_a_language_greets_with_the_sentences_of_the_route_that_greets() -> None:
    assert parse_language_pack(MINIMAL_PACK, instructions="").greetings == ("I'm here.", "I hear you.")


def test_the_hallucinations_of_a_language_file_are_a_set() -> None:
    assert parse_language_pack(MINIMAL_PACK, instructions="").hallucinations == frozenset({"", "you"})


def test_a_language_file_with_an_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(
            MINIMAL_PACK.replace('voice = "neutral_female"', 'voice = "neutral_female"\nvoise = "en_female"'),
            instructions="",
        )


def test_a_language_file_missing_a_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('voice = "neutral_female"', ""), instructions="")


def test_a_route_with_an_unknown_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('name = "yes"', 'name = "yes"\nstop = true'), instructions="")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_announces_two_to_five_agents_at_work(language: Language) -> None:
    assert len(language_pack(language).announcements.at_work) == ANNOUNCED_COUNTS


def every_announcement(language: Language) -> list[str]:
    announcements = language_pack(language).announcements
    return [*announcements.at_work, announcements.many_at_work]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_announcement_of_a_language_is_its_own_sentence(language: Language) -> None:
    sentences = every_announcement(language)
    assert len(set(sentences)) == len(sentences)


def test_a_language_file_without_announcements_is_refused() -> None:
    with pytest.raises(ValidationError):
        _ = parse_language_pack(MINIMAL_PACK.replace('many_at_work = "Many at work."', ""), instructions="")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_is_transcribed_in_itself(language: Language) -> None:
    assert language_pack(language).whisper_code == language
