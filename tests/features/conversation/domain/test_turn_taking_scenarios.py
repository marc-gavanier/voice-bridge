from dataclasses import dataclass

from pytest_bdd import given, parsers, scenarios, then, when

from voice_bridge.features.conversation.domain.turn_taking import (
    Acknowledge,
    Asked,
    AwaitHold,
    AwaitSilence,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    Play,
    SilenceLasted,
    SpeechStarted,
    StartHoldMusic,
    StopHoldMusic,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
    VoiceDetected,
    step,
    unspoken,
)

scenarios("turn_taking.feature")

SPEAKING_AT = 1.0
SILENT_AT = 5.0


@dataclass(frozen=True)
class Turn:
    state: Conversation
    commands: tuple[Command, ...] = ()
    silences: tuple[int, ...] = ()
    holds: tuple[int, ...] = ()


def acknowledgements(commands: tuple[Command, ...]) -> tuple[Acknowledge, ...]:
    return tuple(command for command in commands if isinstance(command, Acknowledge))


def after(turn: Turn, event: Event) -> Turn:
    state, commands = step(turn.state, event)
    awaited = tuple(command.ticket for command in commands if isinstance(command, AwaitSilence))
    holds = tuple(command.ticket for command in commands if isinstance(command, AwaitHold))
    return Turn(state=state, commands=commands, silences=(*turn.silences, *awaited), holds=(*turn.holds, *holds))


def synthesizing_ticket(turn: Turn) -> int:
    assert turn.state.synthesizing is not None
    return turn.state.synthesizing.ticket


@given("Claude is silent", target_fixture="turn")
def claude_is_silent() -> Turn:
    return Turn(state=Conversation())


@given(parsers.parse('Claude is replying "{first}" then "{second}"'), target_fixture="turn")
def claude_is_replying(first: str, second: str) -> Turn:
    return after(Turn(state=Conversation()), Asked(sentences=(first, second)))


@given("the speaker cut Claude off", target_fixture="turn")
def the_speaker_cut_claude_off(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@given("the speaker is talking", target_fixture="turn")
def the_speaker_is_talking() -> Turn:
    return after(Turn(state=Conversation()), VoiceDetected(at=SPEAKING_AT))


@given(parsers.parse('Claude replied "{sentence}"'), target_fixture="turn")
def claude_replied(turn: Turn, sentence: str) -> Turn:
    return after(turn, Asked(sentences=(sentence,)))


def voiced(turn: Turn, sentence: str, duration: float) -> Turn:
    asked = after(turn, Asked(sentences=(sentence,)))
    ticket = next(command.ticket for command in asked.commands if isinstance(command, Synthesize))
    return after(asked, Synthesized(ticket=ticket, pcm=b"", duration=duration, at=SPEAKING_AT))


@given(parsers.parse('Claude said "{sentence}"'), target_fixture="turn")
def claude_said(turn: Turn, sentence: str) -> Turn:
    return voiced(turn, sentence, duration=SILENT_AT - SPEAKING_AT - 1.0)


@given(parsers.parse('Claude is saying "{sentence}"'), target_fixture="turn")
def claude_is_saying(turn: Turn, sentence: str) -> Turn:
    return voiced(turn, sentence, duration=SILENT_AT - SPEAKING_AT + 1.0)


@given("the hold music plays", target_fixture="turn")
def the_hold_music_plays() -> Turn:
    said = after(Turn(state=Conversation()), Transcribed(text="The repository is clean."))
    acknowledged = after(said, SilenceLasted(ticket=said.silences[-1], at=SILENT_AT))
    return after(acknowledged, HoldLasted(ticket=acknowledged.holds[-1]))


@given("the speaker cut in", target_fixture="turn")
def the_speaker_cut_in(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SILENT_AT))


@when("the wait goes on", target_fixture="turn")
def the_wait_goes_on(turn: Turn) -> Turn:
    return after(turn, HoldLasted(ticket=turn.holds[-1]))


@when(parsers.parse('Claude\'s voice for "{sentence}" is ready'), target_fixture="turn")
def claudes_voice_is_ready(turn: Turn, sentence: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == sentence
    return after(turn, Synthesized(ticket=synthesizing_ticket(turn), pcm=b"voice", duration=1.0, at=SILENT_AT))


@when(parsers.parse('Claude\'s voice for "{sentence}" fails'), target_fixture="turn")
def claudes_voice_fails(turn: Turn, sentence: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == sentence
    return after(turn, SynthesisFailed(ticket=synthesizing_ticket(turn)))


@given(parsers.parse('the speaker said "{words}"'), target_fixture="turn")
def the_speaker_said(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words))


@given("the speaker stayed silent", target_fixture="turn")
def the_speaker_stayed_silent(turn: Turn) -> Turn:
    return after(turn, SilenceLasted(ticket=turn.silences[-1], at=SILENT_AT))


@given("the speaker went on", target_fixture="turn")
def the_speaker_went_on(turn: Turn) -> Turn:
    return after(turn, SpeechStarted(at=SPEAKING_AT))


@when(parsers.parse('Claude replies "{sentence}"'), target_fixture="turn")
def claude_replies(turn: Turn, sentence: str) -> Turn:
    return after(turn, Asked(sentences=(sentence,)))


@when("the speaker keeps talking", target_fixture="turn")
def the_speaker_keeps_talking(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT + 0.02))


@when("the speaker starts talking", target_fixture="turn")
def the_speaker_starts_talking(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@when("the speaker only makes a noise", target_fixture="turn")
def the_speaker_makes_a_noise(turn: Turn) -> Turn:
    return after(turn, Transcribed(text="", noise=True))


@when(parsers.parse('the speaker says "{words}"'), target_fixture="turn")
def the_speaker_says(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words))


@when("the speaker stays silent", target_fixture="turn")
def the_speaker_stays_silent(turn: Turn) -> Turn:
    return after(turn, SilenceLasted(ticket=turn.silences[-1], at=SILENT_AT))


@when("the silence after the first words ends", target_fixture="turn")
def the_silence_after_the_first_words_ends(turn: Turn) -> Turn:
    return after(turn, SilenceLasted(ticket=turn.silences[0], at=SILENT_AT))


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
    assert Forward(text=words, interrupted=True) in turn.commands


@then(parsers.parse('Claude hears "{words}"'))
def claude_hears(turn: Turn, words: str) -> None:
    assert Forward(text=words, interrupted=False) in turn.commands


@then(parsers.parse('the bridge acknowledges "{words}"'))
def the_bridge_acknowledges(turn: Turn, words: str) -> None:
    assert Acknowledge(words=words) in turn.commands


@then("the bridge acknowledges nothing")
def the_bridge_acknowledges_nothing(turn: Turn) -> None:
    assert acknowledgements(turn.commands) == ()


@then(parsers.parse('Claude starts saying "{sentence}"'))
def claude_starts_saying(turn: Turn, sentence: str) -> None:
    assert any(isinstance(command, Synthesize) and command.sentence == sentence for command in turn.commands)


@then("the hold music starts")
def the_hold_music_starts(turn: Turn) -> None:
    assert turn.commands == (StartHoldMusic(),)


@then("the hold music stops")
def the_hold_music_stops(turn: Turn) -> None:
    assert StopHoldMusic() in turn.commands


@then("the hold music stops before Claude speaks")
def the_hold_music_stops_before_claude_speaks(turn: Turn) -> None:
    assert turn.commands[:2] == (StopHoldMusic(), Play(pcm=b"voice"))
