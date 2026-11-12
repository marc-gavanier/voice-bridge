from functools import reduce

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    AwaitSilence,
    Command,
    Conversation,
    Event,
    Forward,
    Play,
    SilenceLasted,
    SoundDismissed,
    SpeechEnded,
    SpeechStarted,
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


def test_noise_after_an_interruption_only_resumes_speaking() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), VoiceDetected(at=1.0), Transcribed(text="Merci.", noise=True)) == (
        Synthesize(ticket=1, sentence=FIRST),
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


def test_a_reply_asked_during_an_interruption_waits_behind_the_reply_it_cut() -> None:
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


def test_voice_exactly_when_the_last_sentence_ends_does_not_interrupt() -> None:
    assert (
        last_commands(
            Asked(sentences=(FIRST,)), Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=100.0), VoiceDetected(at=101.0)
        )
        == ()
    )


def test_a_late_synthesis_is_not_played_while_another_one_is_under_way() -> None:
    assert (
        last_commands(
            Asked(sentences=(FIRST,)),
            VoiceDetected(at=1.0),
            Transcribed(text="", noise=True),
            Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=2.0),
        )
        == ()
    )


def test_a_sentence_ending_exactly_at_an_interruption_is_not_saved() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST, SECOND)),
            Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=100.0),
            VoiceDetected(at=101.0),
            Transcribed(text="", noise=True),
        )
    ) == (SECOND,)


def test_a_sentence_playing_at_an_interruption_is_saved_only_once() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            Synthesized(ticket=0, pcm=SOUND, duration=2.0, at=100.0),
            VoiceDetected(at=101.0),
            VoiceDetected(at=101.5),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def forwarded(*events: Event) -> tuple[Forward, ...]:
    return tuple(command for command in commands_of(*events) if isinstance(command, Forward))


def interruptions(*events: Event) -> list[bool]:
    return [forward.interrupted for forward in forwarded(*events)]


def pieces(*events: Event) -> list[int]:
    return [forward.pieces for forward in forwarded(*events)]


def test_speech_after_a_resumed_reply_is_not_marked_as_an_interruption() -> None:
    assert interruptions(
        Asked(sentences=(FIRST,)),
        VoiceDetected(at=1.0),
        Transcribed(text="", noise=True),
        Transcribed(text="Bonjour."),
        SilenceLasted(ticket=0, at=2.0),
    ) == [False]


def test_a_resumed_reply_is_not_resumed_twice() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            VoiceDetected(at=1.0),
            Transcribed(text="", noise=True),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def test_words_after_a_forwarded_interruption_are_not_marked_as_an_interruption() -> None:
    assert interruptions(
        Asked(sentences=(FIRST,)),
        VoiceDetected(at=1.0),
        Transcribed(text="Attends."),
        SilenceLasted(ticket=0, at=2.0),
        Transcribed(text="Encore."),
        SilenceLasted(ticket=1, at=3.0),
    ) == [True, False]


def test_a_forward_counts_the_pieces_it_joins() -> None:
    assert pieces(
        Transcribed(text="Je voudrais..."),
        Transcribed(text="un ticket."),
        SilenceLasted(ticket=1, at=2.0),
    ) == [2]


def test_a_transcript_without_its_start_does_not_hide_words_still_being_said() -> None:
    assert (
        forwarded(
            Transcribed(text="Je voudrais..."),
            SpeechStarted(at=1.0),
            SpeechStarted(at=2.0),
            Transcribed(text="un ticket."),
            SilenceLasted(ticket=1, at=3.0),
        )
        == ()
    )


def test_a_reply_dropped_by_speech_never_comes_back() -> None:
    assert (
        unspoken(
            state_after(
                Asked(sentences=(FIRST,)),
                VoiceDetected(at=1.0),
                Transcribed(text="Attends."),
                Transcribed(text="", noise=True),
            )
        )
        == ()
    )


def test_a_reply_dropped_by_speech_does_not_come_back_after_a_later_noise() -> None:
    assert (
        unspoken(
            state_after(
                Asked(sentences=(FIRST,)),
                VoiceDetected(at=1.0),
                Transcribed(text="Attends."),
                SilenceLasted(ticket=0, at=2.0),
                VoiceDetected(at=3.0),
                Transcribed(text="", noise=True),
            )
        )
        == ()
    )


def test_a_silence_heard_twice_forwards_the_words_once() -> None:
    assert (
        len(
            forwarded(
                Transcribed(text="Bonjour."),
                SilenceLasted(ticket=0, at=2.0),
                SilenceLasted(ticket=0, at=2.0),
            )
        )
        == 1
    )


def test_the_silence_is_counted_from_the_end_of_the_voice() -> None:
    assert last_commands(SpeechStarted(at=1.0), SpeechEnded(at=3.0), Transcribed(text="Bonjour.")) == (
        AwaitSilence(ticket=0, since=3.0),
    )


def test_a_dismissed_sound_does_not_move_the_end_of_the_voice() -> None:
    assert last_commands(
        SpeechStarted(at=1.0),
        SpeechEnded(at=3.0),
        Transcribed(text="Bonjour."),
        SpeechStarted(at=3.5),
        SoundDismissed(),
    ) == (AwaitSilence(ticket=1, since=3.0),)
