from functools import reduce

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Event,
    Forward,
    Play,
    Recording,
    SoundDismissed,
    SpeechEnded,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
    Voiced,
)
from voice_bridge.features.conversation.domain.turn_trace import (
    Counted,
    FinishedTurn,
    Forwarded,
    Report,
    Span,
    Trace,
    Understood,
    close,
    forwarded,
    observe,
)

type Moment = tuple[float, Event | Command]
type History = tuple[Trace, tuple[Report, ...]]

FORWARD = Forward(text="Où en est-on ?", interrupted=False, acknowledging=True)
QUESTION = Understood(route="question", ranking=(("question", 0.8), ("idea", 0.4)))


def advance(history: History, moment: Moment) -> History:
    trace, reports = observe(history[0], *moment)
    return trace, (*history[1], *reports)


def reports_of(*moments: Moment) -> tuple[Report, ...]:
    trace, reports = reduce(advance, moments, (Trace(), ()))
    return (*reports, *close(trace))


def turn_of(*moments: Moment) -> FinishedTurn:
    return next(report for report in reports_of(*moments) if isinstance(report, FinishedTurn))


def steps_of(*moments: Moment) -> tuple[Span, ...]:
    return turn_of(*moments).steps


def step_names(*moments: Moment) -> list[str]:
    return [step.name for step in steps_of(*moments)]


def turn_starts(*moments: Moment) -> list[float]:
    return [report.start for report in reports_of(*moments) if isinstance(report, FinishedTurn)]


def heard(
    at: float = 3.0, ended: float = 2.0, closed: float | None = None, text: str = "Où en est-on ?"
) -> tuple[Moment, ...]:
    return ((ended if closed is None else closed, SpeechEnded(at=ended)), (at, Transcribed(text=text)))


def answered(sentence: str = "Trois notes.", ready: float = 7.0, duration: float = 2.0) -> tuple[Moment, ...]:
    return (
        (6.0, Asked(sentences=(sentence,))),
        (6.0, Synthesize(ticket=0, sentence=sentence)),
        (ready, Voiced(ticket=0, pcm=b"", duration=duration, at=ready)),
        (ready, Play(pcm=b"")),
        (ready, Synthesized(ticket=0, at=ready)),
    )


def test_a_turn_starts_when_the_speakers_voice_ends() -> None:
    assert turn_of(*heard(ended=2.0), (4.0, FORWARD)).start == 2.0


def test_the_end_of_turn_lasts_from_the_end_of_the_voice_to_the_close_of_the_utterance() -> None:
    assert steps_of(*heard(ended=2.0, closed=2.8, at=3.0), (4.0, FORWARD))[0] == Span(
        name="end of turn", start=2.0, end=2.8
    )


def test_the_transcription_lasts_from_the_close_of_the_utterance_to_the_words() -> None:
    assert steps_of(*heard(ended=2.0, closed=2.8, at=3.0), (4.0, FORWARD))[1] == Span(
        name="transcription", start=2.8, end=3.0
    )


def test_the_settle_lasts_from_the_words_to_their_forward() -> None:
    assert steps_of(*heard(at=3.0), (4.0, FORWARD))[-1] == Span(name="settle", start=3.0, end=4.0)


def test_words_said_in_pieces_each_have_their_transcription() -> None:
    assert step_names(*heard(ended=1.0, at=1.5), *heard(ended=2.0, at=3.0), (4.0, FORWARD)) == [
        "end of turn",
        "transcription",
        "end of turn",
        "transcription",
        "settle",
    ]


def test_words_said_in_pieces_start_the_turn_at_the_end_of_the_first_voice() -> None:
    assert turn_of(*heard(ended=1.0, at=1.5), *heard(ended=2.0, at=3.0), (4.0, FORWARD)).start == 1.0


def test_words_without_a_known_end_of_voice_are_transcribed_in_no_time() -> None:
    assert steps_of((3.0, Transcribed(text="Bonjour.")), (4.0, FORWARD))[0] == Span(
        name="transcription", start=3.0, end=3.0
    )


def test_a_forward_without_words_starts_and_settles_at_once() -> None:
    assert turn_of((4.0, FORWARD)) == FinishedTurn(
        start=4.0, end=4.0, steps=(Span(name="settle", start=4.0, end=4.0),), interrupted=False
    )


def test_the_wait_for_claude_lasts_from_the_forward_to_its_reply() -> None:
    assert Span(name="claude", start=4.0, end=6.0) in steps_of(*heard(), (4.0, FORWARD), *answered())


def test_only_the_first_reply_ends_the_wait_for_claude() -> None:
    assert step_names(
        *heard(), (4.0, FORWARD), (6.0, Asked(sentences=("Je regarde.",))), (9.0, Asked(sentences=("Voilà.",)))
    ) == ["end of turn", "transcription", "settle", "claude"]


def synthesis_of(*moments: Moment) -> Span:
    return next(step for step in steps_of(*moments) if step.name.endswith("synthesis"))


def test_a_synthesis_lasts_from_its_order_to_its_voice() -> None:
    synthesis = synthesis_of(*heard(), (4.0, FORWARD), *answered(ready=7.0))
    assert (synthesis.name, synthesis.start, synthesis.end) == ("synthesis", 6.0, 7.0)


def test_a_synthesis_tells_its_rank_its_length_and_the_length_of_its_voice() -> None:
    assert synthesis_of(*heard(), (4.0, FORWARD), *answered(sentence="Trois notes.", duration=2.0)).attributes == (
        ("rank", 0),
        ("characters", 12),
        ("audio.duration", 2.0),
    )


def test_a_failed_synthesis_is_kept_as_such() -> None:
    assert synthesis_of(
        *heard(), (4.0, FORWARD), (6.0, Synthesize(ticket=0, sentence="Trois.")), (8.0, SynthesisFailed(ticket=0))
    ) == Span(name="failed synthesis", start=6.0, end=8.0, attributes=(("rank", 0), ("characters", 6)))


def test_a_recording_tells_no_characters_to_synthesize() -> None:
    assert synthesis_of(
        *heard(),
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence=Recording(name="a.wav", path="/clips/a.wav"))),
        (8.0, SynthesisFailed(ticket=0)),
    ).attributes == (("rank", 0), ("characters", 0))


def synthesis_ranks(*moments: Moment) -> list[object]:
    return [dict(step.attributes)["rank"] for step in steps_of(*moments) if step.name == "synthesis"]


def test_each_sentence_of_a_turn_takes_the_next_rank() -> None:
    assert synthesis_ranks(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Un.")),
        (6.5, Synthesize(ticket=1, sentence="Deux.")),
        (7.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=7.0)),
        (7.0, Synthesized(ticket=1, at=7.0)),
        (8.0, Voiced(ticket=0, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Synthesized(ticket=0, at=8.0)),
    ) == [1, 0]


def second_turn_ranks(*moments: Moment) -> list[object]:
    return [dict(step.attributes)["rank"] for step in turns_of(*moments)[1].steps if step.name == "synthesis"]


def test_the_ranks_start_again_with_each_turn() -> None:
    assert second_turn_ranks(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Un.")),
        (7.0, Voiced(ticket=0, pcm=b"", duration=1.0, at=7.0)),
        (7.0, Synthesized(ticket=0, at=7.0)),
        (14.0, FORWARD),
        (16.0, Synthesize(ticket=1, sentence="Deux.")),
        (17.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=17.0)),
        (17.0, Synthesized(ticket=1, at=17.0)),
    ) == [0]


def test_the_voice_of_a_dropped_synthesis_is_not_a_step() -> None:
    assert step_names(*heard(), (4.0, FORWARD), (7.0, SynthesisFailed(ticket=3))) == [
        "end of turn",
        "transcription",
        "settle",
    ]


def test_a_playback_lasts_as_long_as_its_voice() -> None:
    assert Span(name="playback", start=7.0, end=9.0) in steps_of(*heard(), (4.0, FORWARD), *answered(duration=2.0))


def test_a_sentence_plays_after_the_one_before_it() -> None:
    assert Span(name="playback", start=9.0, end=10.0) in steps_of(
        *heard(),
        (4.0, FORWARD),
        *answered(duration=2.0),
        (7.5, Synthesize(ticket=1, sentence="Et une quatrième.")),
        (8.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Play(pcm=b"")),
        (8.0, Synthesized(ticket=1, at=8.0)),
    )


def test_a_turn_ends_with_the_end_of_its_last_voice() -> None:
    assert turn_of(*heard(), (4.0, FORWARD), *answered(ready=7.0, duration=2.0)).end == 9.0


def test_the_response_lasts_from_the_end_of_the_last_voice_to_the_first_playback() -> None:
    assert (
        turn_of(
            *heard(ended=1.0, at=1.5), *heard(ended=2.0, closed=2.5, at=3.0), (4.0, FORWARD), *answered(ready=7.0)
        ).response
        == 5.0
    )


def test_a_turn_never_played_has_no_response() -> None:
    assert turn_of(*heard(), (4.0, FORWARD)).response is None


def test_words_without_a_known_end_of_voice_are_answered_from_their_forward() -> None:
    assert turn_of((3.0, Transcribed(text="Bonjour.")), (4.0, FORWARD), *answered(ready=7.0)).response == 3.0


def test_a_noise_after_the_words_does_not_move_the_end_of_the_voice() -> None:
    assert (
        turn_of(
            *heard(ended=2.0, at=3.0),
            (3.5, SpeechEnded(at=3.5)),
            (3.8, Transcribed(text="", noise=True)),
            (4.0, FORWARD),
            *answered(ready=7.0),
        ).response
        == 5.0
    )


def test_the_next_turn_is_answered_from_its_own_words() -> None:
    assert turns_of(*heard(), (4.0, FORWARD), (14.0, FORWARD), *answered(ready=17.0))[1].response == 3.0


def test_a_turn_is_finished_when_the_next_words_are_forwarded() -> None:
    assert turn_starts(*heard(ended=2.0), (4.0, FORWARD), *heard(ended=12.0, at=13.0), (14.0, FORWARD)) == [2.0, 12.0]


def test_an_interruption_cuts_the_playback_where_the_voice_was_heard() -> None:
    assert Span(name="playback", start=7.0, end=8.0) in steps_of(
        *heard(), (4.0, FORWARD), *answered(duration=2.0), (8.5, StopPlaying(heard_at=8.0))
    )


def test_an_interruption_drops_the_sentences_not_yet_playing() -> None:
    assert step_names(
        *heard(),
        (4.0, FORWARD),
        *answered(ready=7.0, duration=2.0),
        (7.5, Synthesize(ticket=1, sentence="Et une quatrième.")),
        (8.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Play(pcm=b"")),
        (8.0, Synthesized(ticket=1, at=8.0)),
        (8.5, StopPlaying(heard_at=8.5)),
    ) == [
        "end of turn",
        "transcription",
        "settle",
        "claude",
        "first audio",
        "synthesis",
        "first audio",
        "synthesis",
        "playback",
    ]


def synthesis_starts(*moments: Moment) -> list[float]:
    return [step.start for step in steps_of(*moments) if step.name == "synthesis"]


def test_an_interruption_drops_the_syntheses_under_way() -> None:
    assert synthesis_starts(
        *heard(),
        (4.0, FORWARD),
        *answered(),
        (7.5, Synthesize(ticket=1, sentence="Et une quatrième.")),
        (8.0, StopPlaying(heard_at=8.0)),
        (9.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=9.0)),
        (9.0, Synthesized(ticket=1, at=9.0)),
    ) == [6.0]


def test_an_interrupted_turn_says_so() -> None:
    assert turn_of(*heard(), (4.0, FORWARD), *answered(), (8.0, StopPlaying(heard_at=8.0))).interrupted


def test_an_interruption_is_counted() -> None:
    assert Counted(name="interruption") in reports_of((8.0, StopPlaying(heard_at=8.0)))


def test_a_dismissed_sound_is_counted() -> None:
    assert reports_of((8.0, SoundDismissed())) == (Counted(name="sound dismissed"),)


def test_a_reply_before_any_words_belongs_to_no_turn() -> None:
    assert reports_of(*answered()) == ()


def test_a_noise_alone_does_not_start_the_next_turn() -> None:
    assert (
        turn_of(
            (1.0, SpeechEnded(at=1.0)), (1.5, Transcribed(text="", noise=True)), *heard(ended=2.0), (4.0, FORWARD)
        ).start
        == 2.0
    )


def test_a_noise_after_words_keeps_the_start_of_the_turn() -> None:
    assert (
        turn_of(
            *heard(ended=2.0), (2.5, SpeechEnded(at=2.5)), (3.5, Transcribed(text="", noise=True)), (4.0, FORWARD)
        ).start
        == 2.0
    )


def test_a_noise_is_not_a_transcription_step() -> None:
    assert step_names((1.0, SpeechEnded(at=1.0)), (1.5, Transcribed(text="", noise=True)), (4.0, FORWARD)) == ["settle"]


def test_a_dismissed_sound_alone_does_not_start_the_next_turn() -> None:
    assert turn_of((1.0, SpeechEnded(at=1.0)), (1.5, SoundDismissed()), *heard(ended=2.0), (4.0, FORWARD)).start == 2.0


def test_a_dismissed_sound_after_words_keeps_the_start_of_the_turn() -> None:
    assert turn_of(*heard(ended=2.0), (2.5, SpeechEnded(at=2.5)), (3.0, SoundDismissed()), (4.0, FORWARD)).start == 2.0


def test_closing_without_a_turn_reports_nothing() -> None:
    assert close(Trace()) == ()


def turns_of(*moments: Moment) -> list[FinishedTurn]:
    return [report for report in reports_of(*moments) if isinstance(report, FinishedTurn)]


def test_words_after_a_noise_are_transcribed_from_their_own_arrival() -> None:
    assert steps_of(
        (1.0, SpeechEnded(at=1.0)),
        (1.5, Transcribed(text="", noise=True)),
        (3.0, Transcribed(text="Bonjour.")),
        (4.0, FORWARD),
    )[0] == Span(name="transcription", start=3.0, end=3.0)


def test_a_second_piece_without_its_end_of_voice_is_transcribed_from_its_arrival() -> None:
    assert steps_of(*heard(ended=2.0, at=3.0), (5.0, Transcribed(text="Encore.")), (6.0, FORWARD))[2] == Span(
        name="transcription", start=5.0, end=5.0
    )


def second_turn_names(*moments: Moment) -> list[str]:
    return [step.name for step in turns_of(*moments)[1].steps]


def test_the_next_turn_holds_only_its_own_words() -> None:
    assert second_turn_names(*heard(), (4.0, FORWARD), *heard(ended=12.0, at=13.0), (14.0, FORWARD)) == [
        "end of turn",
        "transcription",
        "settle",
    ]


def test_a_forward_without_new_words_settles_at_once() -> None:
    assert turns_of(*heard(at=3.0), (4.0, FORWARD), (14.0, FORWARD))[1].steps == (
        Span(name="settle", start=14.0, end=14.0),
    )


def test_two_syntheses_under_way_each_end_their_own_step() -> None:
    assert step_names(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Un.")),
        (6.5, Synthesize(ticket=1, sentence="Deux.")),
        (7.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=7.0)),
        (7.0, Synthesized(ticket=1, at=7.0)),
        (8.0, Voiced(ticket=0, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Synthesized(ticket=0, at=8.0)),
    ) == ["settle", "first audio", "synthesis", "first audio", "synthesis"]


def test_a_voice_already_received_is_not_a_second_step() -> None:
    assert step_names(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Un.")),
        (7.0, Voiced(ticket=0, pcm=b"", duration=1.0, at=7.0)),
        (7.0, Synthesized(ticket=0, at=7.0)),
        (8.0, Voiced(ticket=0, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Synthesized(ticket=0, at=8.0)),
    ) == ["settle", "first audio", "synthesis"]


def test_a_sentence_due_to_start_as_the_voice_is_cut_never_plays() -> None:
    assert step_names(
        (4.0, FORWARD),
        (7.0, Voiced(ticket=0, pcm=b"", duration=2.0, at=7.0)),
        (7.0, Play(pcm=b"")),
        (7.0, Synthesized(ticket=0, at=7.0)),
        (8.0, Voiced(ticket=1, pcm=b"", duration=1.0, at=8.0)),
        (8.0, Play(pcm=b"")),
        (8.0, Synthesized(ticket=1, at=8.0)),
        (9.0, StopPlaying(heard_at=9.0)),
    ) == ["settle", "playback"]


def traced(*moments: Moment) -> Trace:
    return reduce(advance, moments, (Trace(), ()))[0]


def test_a_forwarded_utterance_tells_what_was_said_and_understood() -> None:
    trace = traced((2.0, SpeechEnded(at=1.5)), (3.0, Transcribed(text="Où en est-on ?")), (4.0, FORWARD))
    assert forwarded(trace, 4.0, FORWARD, QUESTION, "Voyons.") == Forwarded(
        text="Où en est-on ?",
        interrupted=False,
        understood=QUESTION,
        acknowledgement="Voyons.",
        voice_end=1.5,
        at=4.0,
    )


def test_a_forwarded_utterance_tells_it_interrupted_claude() -> None:
    interrupting = Forward(text="Stop.", interrupted=True, acknowledging=False)
    assert forwarded(traced((4.0, interrupting)), 4.0, interrupting, QUESTION, None).interrupted


def test_an_utterance_forwarded_without_a_turn_ends_its_voice_when_forwarded() -> None:
    assert forwarded(Trace(), 4.0, FORWARD, QUESTION, None).voice_end == 4.0


def first_audio_of(*moments: Moment) -> Span:
    return next(step for step in steps_of(*moments) if step.name == "first audio")


def test_the_first_audio_lasts_from_the_order_to_the_first_piece_of_voice() -> None:
    assert first_audio_of(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.5, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.5)),
    ) == Span(name="first audio", start=6.0, end=6.2, attributes=(("rank", 0), ("characters", 6)))


def test_a_synthesis_lasts_until_its_whole_voice_has_arrived() -> None:
    synthesis = synthesis_of(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.5, Voiced(ticket=0, pcm=b"", duration=0.5, at=6.5)),
        (6.6, Synthesized(ticket=0, at=6.6)),
    )
    assert (synthesis.start, synthesis.end, dict(synthesis.attributes)["audio.duration"]) == (6.0, 6.6, 1.5)


def test_a_synthesis_failed_partway_tells_how_much_voice_it_gave() -> None:
    assert synthesis_of(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.6, SynthesisFailed(ticket=0)),
    ).attributes == (("rank", 0), ("characters", 6), ("audio.duration", 1.0))


def playbacks_of(*moments: Moment) -> list[Span]:
    return [step for step in steps_of(*moments) if step.name == "playback"]


def playback_starts(*moments: Moment) -> list[float]:
    return [step.start for step in playbacks_of(*moments)]


def test_the_pieces_of_one_voice_make_one_playback() -> None:
    assert playbacks_of(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.2, Play(pcm=b"")),
        (6.5, Voiced(ticket=0, pcm=b"", duration=0.5, at=6.5)),
        (6.5, Play(pcm=b"")),
    ) == [Span(name="playback", start=6.2, end=7.7)]


def test_a_piece_arriving_after_the_voice_ran_out_extends_the_playback_from_its_arrival() -> None:
    assert playbacks_of(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.2, Play(pcm=b"")),
        (8.0, Voiced(ticket=0, pcm=b"", duration=0.5, at=8.0)),
        (8.0, Play(pcm=b"")),
    ) == [Span(name="playback", start=6.2, end=8.5)]


def test_the_voice_of_the_next_sentence_makes_its_own_playback() -> None:
    assert playback_starts(
        (4.0, FORWARD),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.2, Play(pcm=b"")),
        (6.5, Voiced(ticket=1, pcm=b"", duration=0.5, at=6.5)),
        (6.5, Play(pcm=b"")),
    ) == [6.2, 7.2]


def test_a_play_without_any_voice_heard_starts_its_own_playback() -> None:
    assert playback_starts((4.0, FORWARD), (6.2, Play(pcm=b"")), (6.5, Play(pcm=b""))) == [6.2, 6.5]


def test_only_the_first_piece_of_a_voice_ends_its_first_audio() -> None:
    assert step_names(
        (4.0, FORWARD),
        (6.0, Synthesize(ticket=0, sentence="Trois.")),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.5, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.5)),
    ) == ["settle", "first audio"]


def test_the_pieces_of_the_second_sentence_extend_its_own_playback() -> None:
    assert playbacks_of(
        (4.0, FORWARD),
        (6.2, Voiced(ticket=0, pcm=b"", duration=1.0, at=6.2)),
        (6.2, Play(pcm=b"")),
        (6.5, Voiced(ticket=1, pcm=b"", duration=0.5, at=6.5)),
        (6.5, Play(pcm=b"")),
        (6.6, Voiced(ticket=1, pcm=b"", duration=0.5, at=6.6)),
        (6.6, Play(pcm=b"")),
    ) == [Span(name="playback", start=6.2, end=7.2), Span(name="playback", start=7.2, end=8.2)]
