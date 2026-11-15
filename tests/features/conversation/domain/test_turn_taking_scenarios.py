from dataclasses import dataclass, replace
from functools import reduce

from pytest_bdd import given, parsers, scenarios, then, when

from voice_bridge.features.conversation.domain.turn_taking import (
    Acknowledge,
    AgentsChanged,
    Announce,
    AnswerLasted,
    Asked,
    AwaitAnswer,
    AwaitHold,
    AwaitSilence,
    CancelSynthesis,
    ClaudeBusy,
    ClaudeIdle,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    Leave,
    Play,
    Recording,
    SilenceLasted,
    SoundDismissed,
    SpeechStarted,
    StartHoldMusic,
    StopHoldMusic,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
    Voiced,
    VoiceDetected,
    step,
    unspoken,
)

scenarios("turn_taking.feature")

SPEAKING_AT = 1.0
SILENT_AT = 5.0
NO_SILENCE = -1
RECORDED = b"recorded"
UNANSWERED = "Claude Code waits for a confirmation on its screen."


@dataclass(frozen=True)
class Turn:
    state: Conversation
    commands: tuple[Command, ...] = ()
    silences: tuple[int, ...] = ()
    holds: tuple[int, ...] = ()
    answers: tuple[int, ...] = ()


def acknowledgements(commands: tuple[Command, ...]) -> tuple[Acknowledge, ...]:
    return tuple(command for command in commands if isinstance(command, Acknowledge))


def after(turn: Turn, event: Event) -> Turn:
    state, commands = step(turn.state, event)
    awaited = tuple(command.ticket for command in commands if isinstance(command, AwaitSilence))
    holds = tuple(command.ticket for command in commands if isinstance(command, AwaitHold))
    answers = tuple(command.ticket for command in commands if isinstance(command, AwaitAnswer))
    return Turn(
        state=state,
        commands=commands,
        silences=(*turn.silences, *awaited),
        holds=(*turn.holds, *holds),
        answers=(*turn.answers, *answers),
    )


def after_all(turn: Turn, *events: Event) -> Turn:
    def combined(before: Turn, event: Event) -> Turn:
        later = after(before, event)
        return replace(later, commands=(*before.commands, *later.commands))

    return reduce(combined, events, replace(turn, commands=()))


def whole_voice(turn: Turn, *, ticket: int, pcm: bytes, duration: float, at: float) -> Turn:
    return after_all(turn, Voiced(ticket=ticket, pcm=pcm, duration=duration, at=at), Synthesized(ticket=ticket, at=at))


def latest_silence(turn: Turn) -> int:
    return (NO_SILENCE, *turn.silences)[-1]


def synthesizing_ticket(turn: Turn) -> int:
    assert turn.state.synthesizing is not None
    return turn.state.synthesizing.ticket


def recording(name: str) -> Recording:
    return Recording(name=name, pcm=RECORDED)


@given("Claude is silent", target_fixture="turn")
def claude_is_silent() -> Turn:
    return Turn(state=Conversation())


@given("Claude Code has not answered since the bridge started", target_fixture="turn")
def claude_code_has_not_answered() -> Turn:
    return Turn(state=Conversation(unanswered=(UNANSWERED,), unanswered_after=10.0))


def unanswered_words(state: Conversation) -> Turn:
    said = after(Turn(state=state), Transcribed(text="Where are we?"))
    return after(said, SilenceLasted(ticket=latest_silence(said), at=SILENT_AT))


@given("the speaker's words reached a Claude Code that never answered", target_fixture="turn")
def words_reached_a_claude_code_that_never_answered() -> Turn:
    return unanswered_words(Conversation(unanswered=(UNANSWERED,), unanswered_after=10.0))


@given(
    "the speaker's words reached a Claude Code that never answered, with a long wait for the music",
    target_fixture="turn",
)
def words_reached_a_claude_code_that_never_answered_with_a_long_wait() -> Turn:
    return unanswered_words(Conversation(unanswered=(UNANSWERED,), unanswered_after=10.0, hold_music_delay=60.0))


@given("Claude Code told the bridge it works", target_fixture="turn")
def claude_code_told_the_bridge_it_works(turn: Turn) -> Turn:
    return after(turn, ClaudeBusy(at=SILENT_AT))


@given("the wait for an answer went on", target_fixture="turn")
def the_wait_for_an_answer_went_on(turn: Turn) -> Turn:
    return after(turn, AnswerLasted(ticket=turn.answers[-1]))


@when("the wait for an answer goes on", target_fixture="turn")
def the_wait_for_an_answer_goes_on(turn: Turn) -> Turn:
    return after(turn, AnswerLasted(ticket=turn.answers[-1]))


@when("the wait for the earlier words goes on", target_fixture="turn")
def the_wait_for_the_earlier_words_goes_on(turn: Turn) -> Turn:
    return after(turn, AnswerLasted(ticket=turn.answers[0]))


@given(parsers.parse('Claude is replying "{first}" then "{second}"'), target_fixture="turn")
def claude_is_replying(first: str, second: str) -> Turn:
    asked = after(Turn(state=Conversation()), Asked(sentences=(first, second)))
    return whole_voice(asked, ticket=synthesizing_ticket(asked), pcm=b"", duration=3.0, at=0.0)


@given("the speaker cut Claude off", target_fixture="turn")
def the_speaker_cut_claude_off(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@given("the speaker is talking", target_fixture="turn")
def the_speaker_is_talking() -> Turn:
    return after(Turn(state=Conversation()), VoiceDetected(at=SPEAKING_AT))


@given("the speaker started talking", target_fixture="turn")
def the_speaker_started_talking(turn: Turn) -> Turn:
    return after(turn, VoiceDetected(at=SPEAKING_AT))


@given(parsers.parse('Claude\'s voice for "{sentence}" was ready'), target_fixture="turn")
def claudes_voice_was_ready(turn: Turn, sentence: str) -> Turn:
    return claudes_voice_is_ready(turn, sentence)


@given(parsers.re(r'Claude replied "(?P<sentence>[^"]*)"$'), target_fixture="turn")
def claude_replied(turn: Turn, sentence: str) -> Turn:
    return after(turn, Asked(sentences=(sentence,)))


def voiced(turn: Turn, sentence: str, duration: float) -> Turn:
    asked = after(turn, Asked(sentences=(sentence,)))
    ticket = next(command.ticket for command in asked.commands if isinstance(command, Synthesize))
    return whole_voice(asked, ticket=ticket, pcm=b"", duration=duration, at=SPEAKING_AT)


@given(parsers.parse('Claude said "{sentence}"'), target_fixture="turn")
def claude_said(turn: Turn, sentence: str) -> Turn:
    return voiced(turn, sentence, duration=SILENT_AT - SPEAKING_AT - 1.0)


@given(parsers.parse('Claude is saying "{sentence}"'), target_fixture="turn")
def claude_is_saying(turn: Turn, sentence: str) -> Turn:
    return voiced(turn, sentence, duration=SILENT_AT - SPEAKING_AT + 1.0)


def working_on(words: str) -> Turn:
    said = after(Turn(state=Conversation()), Transcribed(text=words))
    return after(said, SilenceLasted(ticket=latest_silence(said), at=SILENT_AT))


@given(parsers.parse('Claude is working on "{words}"'), target_fixture="turn")
def claude_is_working_on(words: str) -> Turn:
    return working_on(words)


@given(parsers.parse('Claude replied "{first}" then "{second}"'), target_fixture="turn")
def claude_replied_two_sentences(turn: Turn, first: str, second: str) -> Turn:
    return after(turn, Asked(sentences=(first, second)))


@given("Claude is done", target_fixture="turn")
def claude_was_done(turn: Turn) -> Turn:
    return after(turn, ClaudeIdle())


@when("Claude is done", target_fixture="turn")
def claude_is_done(turn: Turn) -> Turn:
    return after(turn, ClaudeIdle())


@given("Claude started working on its own", target_fixture="turn")
def claude_started_working_on_its_own() -> Turn:
    return after(Turn(state=Conversation()), ClaudeBusy(at=SILENT_AT))


@when("Claude starts working on its own", target_fixture="turn")
def claude_starts_working_on_its_own(turn: Turn) -> Turn:
    return after(turn, ClaudeBusy(at=SILENT_AT))


@given(parsers.parse('Claude said goodbye with "{sentence}"'), target_fixture="turn")
def claude_said_goodbye(turn: Turn, sentence: str) -> Turn:
    return after(turn, Asked(sentences=(sentence,), ending=True))


@given(parsers.parse('Claude is saying goodbye with "{sentence}"'), target_fixture="turn")
def claude_is_saying_goodbye(turn: Turn, sentence: str) -> Turn:
    asked = after(turn, Asked(sentences=(sentence,), ending=True))
    return whole_voice(asked, ticket=synthesizing_ticket(asked), pcm=b"", duration=3.0, at=0.0)


@given("the speaker only made a noise", target_fixture="turn")
def the_speaker_made_a_noise(turn: Turn) -> Turn:
    return after(turn, Transcribed(text="", noise=True))


@given("the speaker made a sound too short to be heard", target_fixture="turn")
def the_speaker_made_a_short_sound(turn: Turn) -> Turn:
    return after(turn, SoundDismissed())


@when("the speaker makes a sound too short to be heard", target_fixture="turn")
def the_speaker_makes_a_short_sound(turn: Turn) -> Turn:
    return after(turn, SoundDismissed())


@given("the hold music plays", target_fixture="turn")
def the_hold_music_plays() -> Turn:
    working = working_on("Where are we?")
    return after(working, HoldLasted(ticket=working.holds[-1]))


@given(parsers.re(r"an agent started and (?P<count>\d+) (?:is|are) at work"), target_fixture="turn")
def an_agent_started(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


@when(parsers.re(r"an agent starts and (?P<count>\d+) (?:is|are) at work"), target_fixture="turn")
def an_agent_starts(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


@given(parsers.re(r"an agent finished and (?P<count>\d+) (?:is|are) left at work"), target_fixture="turn")
def an_agent_finished(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


@when(parsers.re(r"an agent finishes and (?P<count>\d+) (?:is|are) left at work"), target_fixture="turn")
def an_agent_finishes(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


@given(parsers.re(r"an agent was resumed and (?P<count>\d+) (?:is|are) at work"), target_fixture="turn")
def an_agent_was_resumed(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


@when(parsers.re(r"an agent is resumed and (?P<count>\d+) (?:is|are) at work"), target_fixture="turn")
def an_agent_is_resumed(turn: Turn, count: str) -> Turn:
    return after(turn, AgentsChanged(at_work=int(count)))


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
    return whole_voice(turn, ticket=synthesizing_ticket(turn), pcm=b"voice", duration=1.0, at=SILENT_AT)


def first_piece(turn: Turn, sentence: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == sentence
    return after(turn, Voiced(ticket=synthesizing_ticket(turn), pcm=b"voice", duration=3.0, at=0.0))


@when(parsers.parse('the first piece of Claude\'s voice for "{sentence}" is ready'), target_fixture="turn")
def the_first_piece_is_ready(turn: Turn, sentence: str) -> Turn:
    return first_piece(turn, sentence)


@given(parsers.parse('the first piece of Claude\'s voice for "{sentence}" was ready'), target_fixture="turn")
def the_first_piece_was_ready(turn: Turn, sentence: str) -> Turn:
    return first_piece(turn, sentence)


@when(parsers.parse('the rest of Claude\'s voice for "{sentence}" arrives'), target_fixture="turn")
def the_rest_of_the_voice_arrives(turn: Turn, sentence: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == sentence
    return whole_voice(turn, ticket=synthesizing_ticket(turn), pcm=b"voice", duration=1.0, at=SPEAKING_AT)


@when(parsers.parse('Claude\'s voice for "{sentence}" fails'), target_fixture="turn")
def claudes_voice_fails(turn: Turn, sentence: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == sentence
    return after(turn, SynthesisFailed(ticket=synthesizing_ticket(turn)))


@given(parsers.parse('the speaker said "{words}"'), target_fixture="turn")
def the_speaker_said(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words))


@given(parsers.parse('the speaker said "{words}", which its acknowledgement answers'), target_fixture="turn")
def the_speaker_said_words_the_acknowledgement_answers(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words, answered=True))


@given(parsers.parse('the speaker asked to stop with "{words}"'), target_fixture="turn")
def the_speaker_asked_to_stop(turn: Turn, words: str) -> Turn:
    return the_speaker_asks_to_stop(turn, words)


@when(parsers.parse('the speaker asks to stop with "{words}"'), target_fixture="turn")
def the_speaker_asks_to_stop(turn: Turn, words: str) -> Turn:
    return after(turn, Transcribed(text=words, stop_at=SILENT_AT))


@given("the speaker stayed silent", target_fixture="turn")
def the_speaker_stayed_silent(turn: Turn) -> Turn:
    return after(turn, SilenceLasted(ticket=latest_silence(turn), at=SILENT_AT))


@given("the speaker began some words", target_fixture="turn")
def the_speaker_began_some_words(turn: Turn) -> Turn:
    return after(turn, SpeechStarted(at=SPEAKING_AT))


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
    return after(turn, SilenceLasted(ticket=latest_silence(turn), at=SILENT_AT))


@when("the silence after the first words ends", target_fixture="turn")
def the_silence_after_the_first_words_ends(turn: Turn) -> Turn:
    return after(turn, SilenceLasted(ticket=turn.silences[0], at=SILENT_AT))


@then("Claude's voice stops")
def claudes_voice_stops(turn: Turn) -> None:
    assert StopPlaying(heard_at=SPEAKING_AT) in turn.commands


@then("Claude's voice plays")
def claudes_voice_plays(turn: Turn) -> None:
    assert Play(pcm=b"voice") in turn.commands


@then("Claude's voice does not play")
def claudes_voice_does_not_play(turn: Turn) -> None:
    assert not any(isinstance(command, Play) for command in turn.commands)


@then("the synthesis under way is abandoned")
def the_synthesis_under_way_is_abandoned(turn: Turn) -> None:
    assert any(isinstance(command, CancelSynthesis) for command in turn.commands)


@then("no synthesis is abandoned")
def no_synthesis_is_abandoned(turn: Turn) -> None:
    assert not any(isinstance(command, CancelSynthesis) for command in turn.commands)


@then("Claude's voice stops when the stop is understood")
def claudes_voice_stops_when_the_stop_is_understood(turn: Turn) -> None:
    assert StopPlaying(heard_at=SILENT_AT) in turn.commands


@then("Claude's voice is not stopped")
def claudes_voice_is_not_stopped(turn: Turn) -> None:
    assert not any(isinstance(command, StopPlaying) for command in turn.commands)


@then("nothing happens")
def nothing_happens(turn: Turn) -> None:
    assert turn.commands == ()


@then(parsers.parse('Claude still has to say "{first}" then "{second}"'))
def claude_still_has_to_say(turn: Turn, first: str, second: str) -> None:
    assert unspoken(turn.state) == (first, second)


@then("Claude has nothing left to say")
def claude_has_nothing_left_to_say(turn: Turn) -> None:
    assert unspoken(turn.state) == ()


def forwarded(turn: Turn) -> Forward:
    return next(command for command in turn.commands if isinstance(command, Forward))


@then(parsers.parse('Claude hears "{words}" as an interruption'))
def claude_hears_an_interruption(turn: Turn, words: str) -> None:
    assert (forwarded(turn).text, forwarded(turn).interrupted) == (words, True)


@then(parsers.parse('Claude hears "{words}"'))
def claude_hears(turn: Turn, words: str) -> None:
    assert (forwarded(turn).text, forwarded(turn).interrupted) == (words, False)


@then("Claude hears nothing yet")
def claude_hears_nothing_yet(turn: Turn) -> None:
    assert not any(isinstance(command, Forward) for command in turn.commands)


@then("Claude says nothing yet")
def claude_says_nothing_yet(turn: Turn) -> None:
    assert not any(isinstance(command, Synthesize) for command in turn.commands)


@then(parsers.parse('Claude hears "{words}" with an acknowledgement to come'))
def claude_hears_with_an_acknowledgement(turn: Turn, words: str) -> None:
    assert (forwarded(turn).text, forwarded(turn).acknowledging) == (words, True)


@then(parsers.parse('Claude hears "{words}" with no acknowledgement to come'))
def claude_hears_without_an_acknowledgement(turn: Turn, words: str) -> None:
    assert (forwarded(turn).text, forwarded(turn).acknowledging) == (words, False)


@then(parsers.parse('the bridge acknowledges "{words}"'))
def the_bridge_acknowledges(turn: Turn, words: str) -> None:
    assert Acknowledge(words=words) in turn.commands


@then("the bridge acknowledges nothing")
def the_bridge_acknowledges_nothing(turn: Turn) -> None:
    assert acknowledgements(turn.commands) == ()


@then(parsers.parse('Claude starts saying "{sentence}"'))
def claude_starts_saying(turn: Turn, sentence: str) -> None:
    assert any(isinstance(command, Synthesize) and command.sentence == sentence for command in turn.commands)


@then("the hold music waits for the end of that voice")
def the_hold_music_waits_for_the_end_of_that_voice(turn: Turn) -> None:
    assert [command.after for command in turn.commands if isinstance(command, AwaitHold)] == [1.0]


@then("the bridge waits for Claude Code to answer")
def the_bridge_waits_for_claude_code_to_answer(turn: Turn) -> None:
    assert [command.after for command in turn.commands if isinstance(command, AwaitAnswer)] == [10.0]


@then("the bridge does not wait for Claude Code to answer")
def the_bridge_does_not_wait_for_claude_code_to_answer(turn: Turn) -> None:
    assert not any(isinstance(command, AwaitAnswer) for command in turn.commands)


@then("the bridge says that Claude Code does not answer")
def the_bridge_says_that_claude_code_does_not_answer(turn: Turn) -> None:
    assert any(isinstance(command, Synthesize) and command.sentence == UNANSWERED for command in turn.commands)


@then("Claude no longer counts as working")
def claude_no_longer_counts_as_working(turn: Turn) -> None:
    assert not turn.state.working


@then("the bridge waits for the hold music")
def the_bridge_waits_for_the_hold_music(turn: Turn) -> None:
    assert any(isinstance(command, AwaitHold) for command in turn.commands)


@then("the bridge waits for the hold music from now on")
def the_bridge_waits_for_the_hold_music_from_now_on(turn: Turn) -> None:
    assert [command.after for command in turn.commands if isinstance(command, AwaitHold)] == [0.0]


@then("the hold music is not stopped again")
def the_hold_music_is_not_stopped_again(turn: Turn) -> None:
    assert StopHoldMusic() not in turn.commands


@then("the bridge waits for no hold music")
def the_bridge_waits_for_no_hold_music(turn: Turn) -> None:
    assert not any(isinstance(command, AwaitHold) for command in turn.commands)


@then("the hold music starts")
def the_hold_music_starts(turn: Turn) -> None:
    assert turn.commands == (StartHoldMusic(),)


@then("the hold music stops")
def the_hold_music_stops(turn: Turn) -> None:
    assert StopHoldMusic() in turn.commands


@then("the hold music stops before Claude speaks")
def the_hold_music_stops_before_claude_speaks(turn: Turn) -> None:
    assert turn.commands[:2] == (StopHoldMusic(), Play(pcm=b"voice"))


def leaves(turn: Turn) -> tuple[Leave, ...]:
    return tuple(command for command in turn.commands if isinstance(command, Leave))


@then("the bridge leaves when that voice ends")
def the_bridge_leaves_when_that_voice_ends(turn: Turn) -> None:
    assert leaves(turn) == (Leave(until=SILENT_AT + 1.0),)


@then("the bridge leaves at once")
def the_bridge_leaves_at_once(turn: Turn) -> None:
    assert leaves(turn) == (Leave(until=0.0),)


@then("the bridge does not leave yet")
def the_bridge_does_not_leave_yet(turn: Turn) -> None:
    assert leaves(turn) == ()


@then("the session goes on")
def the_session_goes_on(turn: Turn) -> None:
    assert not turn.state.ending


def announcements(commands: tuple[Command, ...]) -> tuple[Announce, ...]:
    return tuple(command for command in commands if isinstance(command, Announce))


def position(commands: tuple[Command, ...], kind: type[Command]) -> int:
    return next(index for index, command in enumerate(commands) if isinstance(command, kind))


@then(parsers.parse("the bridge announces {count:d} at work only"))
def the_bridge_announces_only(turn: Turn, count: int) -> None:
    assert announcements(turn.commands) == (Announce(at_work=count),)


@then(parsers.parse("the bridge announces {count:d} at work"))
def the_bridge_announces(turn: Turn, count: int) -> None:
    assert Announce(at_work=count) in turn.commands


@then("the bridge announces nothing")
def the_bridge_announces_nothing(turn: Turn) -> None:
    assert announcements(turn.commands) == ()


@then("the announcement follows Claude's voice")
def the_announcement_follows_claudes_voice(turn: Turn) -> None:
    assert position(turn.commands, Play) < position(turn.commands, Announce)


@then("the announcement follows the acknowledgement")
def the_announcement_follows_the_acknowledgement(turn: Turn) -> None:
    assert position(turn.commands, Acknowledge) < position(turn.commands, Announce)


@then("the hold music stops before the announcement")
def the_hold_music_stops_before_the_announcement(turn: Turn) -> None:
    assert turn.commands[:2] == (StopHoldMusic(), Announce(at_work=2))


@when(parsers.parse('Claude plays the recording "{name}"'), target_fixture="turn")
def claude_plays_the_recording(turn: Turn, name: str) -> Turn:
    return after(turn, Asked(sentences=(recording(name),)))


@given(parsers.parse('Claude played the recording "{name}"'), target_fixture="turn")
def claude_played_the_recording(turn: Turn, name: str) -> Turn:
    return claude_plays_the_recording(turn, name)


@given(parsers.parse('Claude is playing the recording "{name}"'), target_fixture="turn")
def claude_is_playing_the_recording(name: str) -> Turn:
    asked = after(Turn(state=Conversation()), Asked(sentences=(recording(name),)))
    return whole_voice(asked, ticket=synthesizing_ticket(asked), pcm=RECORDED, duration=3.0, at=0.0)


@when(parsers.parse('the recording "{name}" is ready'), target_fixture="turn")
def the_recording_is_ready(turn: Turn, name: str) -> Turn:
    assert turn.state.synthesizing is not None
    assert turn.state.synthesizing.sentence == recording(name)
    return whole_voice(turn, ticket=synthesizing_ticket(turn), pcm=b"voice", duration=1.0, at=SILENT_AT)


@then(parsers.parse('Claude starts saying the recording "{name}"'))
def claude_starts_saying_the_recording(turn: Turn, name: str) -> None:
    assert Synthesize(ticket=synthesizing_ticket(turn), sentence=recording(name)) in turn.commands


@then(parsers.parse('Claude still has to say "{first}" and "{second}" before the recording "{name}"'))
def claude_still_has_to_say_then_the_recording(turn: Turn, first: str, second: str, name: str) -> None:
    assert unspoken(turn.state) == (first, second, recording(name))
