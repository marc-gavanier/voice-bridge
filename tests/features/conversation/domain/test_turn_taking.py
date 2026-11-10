from functools import reduce

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Conversation,
    Event,
    Forward,
    Play,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
    VoiceDetected,
    step,
    unspoken,
)

FIRST = "Première phrase assez longue."
SECOND = "Deuxième phrase assez longue."
SOUND = b"\x01\x00" * 48000


type History = tuple[Conversation, tuple[Command, ...]]


def advance(history: History, event: Event) -> History:
    state, commands = step(history[0], event)
    return state, (*history[1], *commands)


def converse(*events: Event) -> History:
    return reduce(advance, events, (Conversation(), ()))


def state_after(*events: Event) -> Conversation:
    return converse(*events)[0]


def commands_of(*events: Event) -> tuple[Command, ...]:
    return converse(*events)[1]


def last_commands(*events: Event) -> tuple[Command, ...]:
    return step(state_after(*events[:-1]), events[-1])[1]


def test_asking_starts_synthesizing_the_first_sentence() -> None:
    assert commands_of(Asked(sentences=(FIRST, SECOND))) == (Synthesize(ticket=0, sentence=FIRST),)


def test_a_synthesized_sentence_is_played() -> None:
    assert Play(pcm=SOUND) in last_commands(
        Asked(sentences=(FIRST,)), Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=10.0)
    )


def test_the_next_sentence_is_synthesized_once_the_previous_one_is_ready() -> None:
    assert Synthesize(ticket=1, sentence=SECOND) in last_commands(
        Asked(sentences=(FIRST, SECOND)), Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=10.0)
    )


def test_a_failed_synthesis_moves_on_to_the_next_sentence() -> None:
    assert last_commands(Asked(sentences=(FIRST, SECOND)), SynthesisFailed(ticket=0)) == (
        Synthesize(ticket=1, sentence=SECOND),
    )


def test_voice_while_the_bridge_is_silent_does_not_interrupt() -> None:
    assert last_commands(VoiceDetected(at=1.0)) == ()


def test_voice_while_the_bridge_talks_stops_the_playback() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), VoiceDetected(at=1.0)) == (StopPlaying(heard_at=1.0),)


def test_noise_after_an_interruption_resumes_the_unspoken_sentences() -> None:
    assert unspoken(
        state_after(Asked(sentences=(FIRST, SECOND)), VoiceDetected(at=1.0), Transcribed(text="Merci.", noise=True))
    ) == (FIRST, SECOND)


def test_noise_after_an_interruption_only_resumes_speaking() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), VoiceDetected(at=1.0), Transcribed(text="Merci.", noise=True)) == (
        Synthesize(ticket=1, sentence=FIRST),
    )


def test_speech_after_an_interruption_drops_the_rest_of_the_reply() -> None:
    assert (
        unspoken(state_after(Asked(sentences=(FIRST, SECOND)), VoiceDetected(at=1.0), Transcribed(text="Attends.")))
        == ()
    )


def test_speech_after_an_interruption_is_forwarded_as_an_interruption() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), VoiceDetected(at=1.0), Transcribed(text="Attends.")) == (
        Forward(text="Attends.", interrupted=True),
    )


def test_repeated_interruptions_keep_the_first_saved_sentences() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            VoiceDetected(at=1.0),
            VoiceDetected(at=1.1),
            Transcribed(text="Merci.", noise=True),
        )
    ) == (FIRST,)


def test_interrupting_mid_playback_resumes_the_sentence_being_played() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            Synthesized(ticket=0, pcm=SOUND, duration=2.0, at=100.0),
            VoiceDetected(at=101.0),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def test_finished_sentences_are_not_resumed() -> None:
    assert (
        unspoken(
            state_after(
                Asked(sentences=(FIRST,)),
                Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=100.0),
                VoiceDetected(at=105.0),
                Transcribed(text="", noise=True),
            )
        )
        == ()
    )


def test_a_transcript_without_interruption_is_forwarded() -> None:
    assert commands_of(Transcribed(text="Bonjour.")) == (Forward(text="Bonjour.", interrupted=False),)


def test_noise_without_interruption_is_dropped() -> None:
    assert commands_of(Transcribed(text="Merci.", noise=True)) == ()


def test_a_reply_asked_during_an_interruption_can_be_interrupted_too() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            VoiceDetected(at=1.0),
            Asked(sentences=(SECOND,)),
            VoiceDetected(at=1.5),
            Transcribed(text="Merci.", noise=True),
        )
    ) == (FIRST, SECOND)


def test_repeated_interruptions_do_not_duplicate_the_sentence_being_synthesized() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            VoiceDetected(at=1.0),
            VoiceDetected(at=1.1),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def test_a_synthesis_finished_after_an_interruption_is_not_played() -> None:
    assert (
        last_commands(
            Asked(sentences=(FIRST,)), VoiceDetected(at=1.0), Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=2.0)
        )
        == ()
    )


def test_a_synthesis_failed_after_an_interruption_changes_nothing() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), VoiceDetected(at=1.0), SynthesisFailed(ticket=0)) == ()
