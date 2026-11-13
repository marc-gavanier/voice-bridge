from functools import reduce

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    AwaitHold,
    AwaitSilence,
    ClaudeBusy,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    Leave,
    Play,
    SilenceLasted,
    SoundDismissed,
    SpeechEnded,
    SpeechStarted,
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

FIRST = "Première phrase assez longue."
SECOND = "Deuxième phrase assez longue."
SOUND = b"\x01\x00" * 48000
HEARD = Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=0.5)


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
    assert last_commands(
        Asked(sentences=(FIRST,)), HEARD, VoiceDetected(at=1.0), Transcribed(text="Merci.", noise=True)
    ) == (Synthesize(ticket=1, sentence=FIRST),)


def test_repeated_interruptions_keep_the_first_saved_sentences() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            HEARD,
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
            HEARD,
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
            HEARD,
            VoiceDetected(at=1.0),
            VoiceDetected(at=1.1),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def test_a_synthesis_finished_after_an_interruption_is_not_played() -> None:
    assert (
        last_commands(
            Asked(sentences=(FIRST,)),
            HEARD,
            VoiceDetected(at=1.0),
            Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=2.0),
        )
        == ()
    )


def test_a_synthesis_failed_after_an_interruption_changes_nothing() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), HEARD, VoiceDetected(at=1.0), SynthesisFailed(ticket=0)) == ()


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
            HEARD,
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
        HEARD,
        VoiceDetected(at=1.0),
        Transcribed(text="", noise=True),
        Transcribed(text="Bonjour."),
        SilenceLasted(ticket=0, at=2.0),
    ) == [False]


def test_a_resumed_reply_is_not_resumed_twice() -> None:
    assert unspoken(
        state_after(
            Asked(sentences=(FIRST,)),
            HEARD,
            VoiceDetected(at=1.0),
            Transcribed(text="", noise=True),
            Transcribed(text="", noise=True),
        )
    ) == (FIRST,)


def test_words_after_a_forwarded_interruption_are_not_marked_as_an_interruption() -> None:
    assert interruptions(
        Asked(sentences=(FIRST,)),
        HEARD,
        VoiceDetected(at=1.0),
        Transcribed(text="Attends."),
        SilenceLasted(ticket=0, at=2.0),
        Transcribed(text="Encore."),
        SilenceLasted(ticket=2, at=3.0),
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
                HEARD,
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
                HEARD,
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
        AwaitSilence(ticket=0, until=3.0),
    )


def test_a_dismissed_sound_does_not_move_the_end_of_the_voice() -> None:
    assert last_commands(
        SpeechStarted(at=1.0),
        SpeechEnded(at=3.0),
        Transcribed(text="Bonjour."),
        SpeechStarted(at=3.5),
        SoundDismissed(),
    ) == (AwaitSilence(ticket=1, until=3.0),)


THIRD = "Troisième phrase assez longue."


def announced(*events: Event) -> tuple[Event, ...]:
    return (
        Asked(sentences=("Je regarde.",)),
        Synthesized(ticket=0, pcm=SOUND, duration=0.5, at=0.0),
        ClaudeBusy(at=0.0),
        *events,
    )


def test_the_hold_music_is_stopped_only_once() -> None:
    assert StopHoldMusic() not in last_commands(
        *announced(
            HoldLasted(ticket=0),
            Asked(sentences=(FIRST,)),
            Synthesized(ticket=1, pcm=SOUND, duration=1.0, at=10.0),
            Asked(sentences=(SECOND,)),
            Synthesized(ticket=2, pcm=SOUND, duration=1.0, at=20.0),
        )
    )


def test_the_hold_music_starts_only_once_for_a_wait() -> None:
    assert last_commands(*announced(HoldLasted(ticket=0), HoldLasted(ticket=0))) == ()


def test_words_forwarded_while_claude_works_bring_the_hold_music_back_at_once() -> None:
    assert AwaitHold(ticket=2, after=0.0) in last_commands(
        *announced(Transcribed(text="Et les journaux aussi."), SilenceLasted(ticket=1, at=2.0))
    )


def test_the_speaker_talking_after_the_announcement_cancels_the_coming_hold_music() -> None:
    assert last_commands(*announced(VoiceDetected(at=2.0), HoldLasted(ticket=0))) == ()


def test_words_before_the_goodbye_is_voiced_keep_the_session_going() -> None:
    assert not any(
        isinstance(command, Leave)
        for command in last_commands(
            Asked(sentences=("Au revoir.",), ending=True),
            Transcribed(text="Attends."),
            SilenceLasted(ticket=0, at=1.0),
            Synthesized(ticket=0, pcm=SOUND, duration=1.0, at=2.0),
        )
    )


def test_words_drop_every_sentence_of_the_reply_they_cut() -> None:
    assert (
        unspoken(
            state_after(
                Asked(sentences=(FIRST, SECOND, THIRD)),
                HEARD,
                VoiceDetected(at=1.0),
                Transcribed(text="Attends."),
            )
        )
        == ()
    )


def test_a_reply_after_an_interruption_is_scheduled_after_its_own_start() -> None:
    assert AwaitHold(ticket=2, after=1.0) in last_commands(
        Asked(sentences=(FIRST,)),
        HEARD,
        VoiceDetected(at=1.0),
        Transcribed(text="Attends."),
        SilenceLasted(ticket=0, at=2.0),
        Asked(sentences=("Je regarde.",)),
        Synthesized(ticket=1, pcm=SOUND, duration=1.0, at=1.25),
    )


def test_a_reply_arriving_after_an_interruption_waits_for_the_speakers_words() -> None:
    assert last_commands(Asked(sentences=(FIRST,)), HEARD, VoiceDetected(at=1.0), Asked(sentences=(SECOND,))) == ()


def test_a_reply_heard_before_the_speakers_words_does_not_make_the_next_one_cuttable() -> None:
    assert StopPlaying(heard_at=3.0) not in last_commands(
        Asked(sentences=(FIRST,)),
        HEARD,
        Transcribed(text="Et ensuite ?"),
        SilenceLasted(ticket=0, at=2.0),
        Asked(sentences=(SECOND,)),
        VoiceDetected(at=3.0),
    )


def test_stopping_the_hold_music_leaves_it_off() -> None:
    assert (
        state_after(
            *announced(
                HoldLasted(ticket=0),
                Asked(sentences=(FIRST,)),
                Synthesized(ticket=1, pcm=SOUND, duration=1.0, at=10.0),
            )
        ).holding
        is False
    )


def test_forwarding_the_words_leaves_the_bridge_no_longer_hearing_and_the_next_reply_unheard() -> None:
    state = state_after(Asked(sentences=(FIRST,)), HEARD, Transcribed(text="Bonjour."), SilenceLasted(ticket=0, at=2.0))
    assert (state.hearing, state.reply_heard) == (False, False)


PATIENT = Conversation(settle=1.25, hold_music_delay=2.0)


def patient_commands(*events: Event) -> tuple[Command, ...]:
    return reduce(advance, events, (PATIENT, ()))[1]


def test_the_silence_lasts_the_settle_after_the_end_of_the_voice() -> None:
    assert patient_commands(SpeechStarted(at=1.0), SpeechEnded(at=3.0), Transcribed(text="Bonjour."))[-1] == (
        AwaitSilence(ticket=0, until=4.25, lasting=1.25)
    )


def test_the_whole_settle_is_awaited_when_the_end_of_the_voice_is_unknown() -> None:
    assert patient_commands(Transcribed(text="Bonjour.")) == (AwaitSilence(ticket=0, until=None, lasting=1.25),)


def test_the_hold_music_waits_its_delay_after_the_reply() -> None:
    assert patient_commands(
        ClaudeBusy(at=0.0),
        Asked(sentences=("Je regarde.",)),
        Synthesized(ticket=0, pcm=SOUND, duration=0.5, at=0.0),
    )[-1] == AwaitHold(ticket=1, after=2.5)


def test_a_stop_drops_the_sentences_still_waiting_for_their_voice() -> None:
    assert (
        unspoken(
            state_after(Asked(sentences=(FIRST, SECOND, "Troisième.")), HEARD, Transcribed(text="Stop.", stop_at=1.0))
        )
        == ()
    )
