from dataclasses import dataclass

from pytest_bdd import given, parsers, scenarios, then, when

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Conversation,
    Event,
    Forward,
    StopPlaying,
    Transcribed,
    VoiceDetected,
    step,
    unspoken,
)

scenarios("turn_taking.feature")

SPEAKING_AT = 1.0


@dataclass(frozen=True)
class Turn:
    state: Conversation
    commands: tuple[Command, ...] = ()


def after(turn: Turn, event: Event) -> Turn:
    state, commands = step(turn.state, event)
    return Turn(state=state, commands=commands)


@given("Claude is silent", target_fixture="turn")
def claude_is_silent() -> Turn:
    return Turn(state=Conversation())


@given(parsers.parse('Claude is replying "{first}" then "{second}"'), target_fixture="turn")
def claude_is_replying(first: str, second: str) -> Turn:
    return after(Turn(state=Conversation()), Asked(sentences=(first, second)))


@given("the speaker cut Claude off", target_fixture="turn")
def the_speaker_cut_claude_off(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@when("the speaker starts talking", target_fixture="turn")
def the_speaker_starts_talking(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@when("the speaker only makes a noise", target_fixture="turn")
def the_speaker_makes_a_noise(turn: Turn) -> Turn:
    return after(turn, Transcribed(text="", noise=True))


@when(parsers.parse('the speaker says "{words}"'), target_fixture="turn")
def the_speaker_says(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words))


@then("Claude's voice stops")
def claudes_voice_stops(turn: Turn) -> None:
    assert turn.commands == (StopPlaying(heard_at=SPEAKING_AT),)


@then("nothing happens")
def nothing_happens(turn: Turn) -> None:
    assert turn.commands == ()


@then(parsers.parse('Claude still has to say "{first}" then "{second}"'))
def claude_still_has_to_say(turn: Turn, first: str, second: str) -> None:
    assert unspoken(turn.state) == (first, second)


@then("Claude has nothing left to say")
def claude_has_nothing_left_to_say(turn: Turn) -> None:
    assert unspoken(turn.state) == ()


@then(parsers.parse('Claude hears "{words}" as an interruption'))
def claude_hears_an_interruption(turn: Turn, words: str) -> None:
    assert turn.commands == (Forward(text=words, interrupted=True),)


@then(parsers.parse('Claude hears "{words}"'))
def claude_hears(turn: Turn, words: str) -> None:
    assert turn.commands == (Forward(text=words, interrupted=False),)
