from functools import reduce

import pytest

from voice_bridge.features.hearing.domain.utterance import (
    Closing,
    Dismissed,
    Frame,
    Kept,
    Listening,
    UtteranceRules,
    close,
    hear,
    is_speaking,
    needs_turn_check,
    turn_checked,
)

PACKET = 0.02
PACKET_BYTES = 1920
RULES = UtteranceRules(silence=0.8, longest=30.0, shortest_voice=0.2, preroll=0.1, barge_in=0.1, barge_window=1.0)


def frame(*, voiced: bool, at: float) -> Frame:
    return Frame(pcm=bytes(PACKET_BYTES), voiced=voiced, at=at, duration=PACKET)


def listen(*runs: tuple[bool, int], rules: UtteranceRules = RULES) -> tuple[Listening, float]:
    voicing = [voiced for voiced, count in runs for _ in range(count)]
    frames = [frame(voiced=voiced, at=(index + 1) * PACKET) for index, voiced in enumerate(voicing)]
    return reduce(lambda state, each: hear(state, each, rules), frames, Listening()), len(frames) * PACKET


VOICE, SILENCE = True, False


def closed(*runs: tuple[bool, int], rules: UtteranceRules = RULES) -> Closing | None:
    state, now = listen(*runs, rules=rules)
    return close(state, now, rules)[1]


def test_nothing_is_closed_while_the_speaker_talks() -> None:
    assert closed((VOICE, 50)) is None


def test_an_utterance_is_closed_after_a_silence() -> None:
    assert closed((VOICE, 50), (SILENCE, 45)) is not None


def kept(closing: Closing | None) -> bytes:
    return closing.pcm if isinstance(closing, Kept) else b""


def test_the_utterance_holds_all_the_voice() -> None:
    assert len(kept(closed((VOICE, 50), (SILENCE, 45)))) >= 50 * PACKET_BYTES


def test_an_utterance_is_closed_only_once() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 45))
    assert close(close(state, now, RULES)[0], now, RULES)[1] is None


def test_a_short_noise_is_dismissed() -> None:
    assert isinstance(closed((VOICE, 3), (SILENCE, 45)), Dismissed)


def dismissed_voice(closing: Closing | None) -> float:
    return closing.voice if isinstance(closing, Dismissed) else -1.0


def test_a_dismissed_sound_tells_how_much_voice_it_held() -> None:
    assert dismissed_voice(closed((VOICE, 3), (SILENCE, 45))) == pytest.approx(3 * PACKET)


def dismissed_duration(closing: Closing | None) -> float:
    return closing.duration if isinstance(closing, Dismissed) else -1.0


def test_a_dismissed_sound_tells_how_long_it_lasted() -> None:
    assert dismissed_duration(closed((VOICE, 3), (SILENCE, 45))) == pytest.approx(48 * PACKET)


def test_silence_alone_is_not_an_utterance() -> None:
    assert closed((SILENCE, 200)) is None


def test_the_utterance_keeps_the_audio_just_before_the_voice() -> None:
    assert len(kept(closed((SILENCE, 20), (VOICE, 50), (SILENCE, 45)))) >= (50 + 45 + 5) * PACKET_BYTES


def test_a_long_speech_is_closed_at_the_longest_duration() -> None:
    assert closed((VOICE, 60), rules=UtteranceRules(longest=1.0, shortest_voice=0.2)) is not None


def test_a_brief_voice_is_not_speaking_yet() -> None:
    assert not is_speaking(listen((VOICE, 2))[0], RULES)


def test_a_sustained_voice_is_speaking() -> None:
    assert is_speaking(listen((VOICE, 12))[0], RULES)


def test_speaking_stops_after_a_long_silence() -> None:
    assert not is_speaking(listen((VOICE, 20), (SILENCE, 60))[0], RULES)


def test_speaking_tolerates_short_dips_between_syllables() -> None:
    dips = [(VOICE, 4), (SILENCE, 1)] * 8
    assert is_speaking(listen(*dips, rules=UtteranceRules())[0], UtteranceRules())


def test_by_default_speaking_needs_more_than_four_tenths_of_a_second() -> None:
    assert not is_speaking(listen((VOICE, 20), rules=UtteranceRules())[0], UtteranceRules())


def test_by_default_half_a_second_of_voice_is_speaking() -> None:
    assert is_speaking(listen((VOICE, 25), rules=UtteranceRules())[0], UtteranceRules())


def test_a_lone_packet_long_after_the_speaker_stopped_is_not_speaking() -> None:
    state, _ = listen((VOICE, 25), rules=UtteranceRules())
    assert not is_speaking(hear(state, frame(voiced=True, at=3.0), UtteranceRules()), UtteranceRules())


QUARTER = UtteranceRules(silence=0.5, longest=1.0, shortest_voice=0.5, preroll=0.5, barge_in=0.5, barge_window=1.0)


def quarter(*, voiced: bool, at: float, pcm: bytes = b"\x01\x00") -> Frame:
    return Frame(pcm=pcm, voiced=voiced, at=at, duration=0.25)


def quarters(*moments: float, voiced: bool, pcm: bytes = b"\x01\x00") -> tuple[Frame, ...]:
    return tuple(quarter(voiced=voiced, at=at, pcm=pcm) for at in moments)


def heard_quarters(*frames: Frame) -> Listening:
    return reduce(lambda state, each: hear(state, each, QUARTER), frames, Listening())


def test_the_preroll_keeps_just_enough_audio_before_the_voice() -> None:
    state = heard_quarters(*quarters(0.25, 0.5, 0.75, 1.0, voiced=False, pcm=b"s"))
    assert hear(state, quarter(voiced=True, at=1.25, pcm=b"v"), QUARTER).utterance == (
        quarter(voiced=False, at=0.75, pcm=b"s"),
        quarter(voiced=False, at=1.0, pcm=b"s"),
        quarter(voiced=True, at=1.25, pcm=b"v"),
    )


def test_the_preroll_is_emptied_once_the_voice_starts() -> None:
    state = heard_quarters(quarter(voiced=False, at=0.25), quarter(voiced=True, at=0.5))
    assert state.preroll == ()


def test_a_frame_exactly_one_window_old_no_longer_counts_as_recent() -> None:
    assert heard_quarters(quarter(voiced=True, at=0.0), quarter(voiced=True, at=1.0)).recent == (
        quarter(voiced=True, at=1.0),
    )


def test_an_utterance_goes_on_at_exactly_the_silence() -> None:
    assert close(heard_quarters(quarter(voiced=True, at=0.25), quarter(voiced=True, at=0.5)), 1.0, QUARTER)[1] is None


def test_an_utterance_reaching_exactly_the_longest_duration_is_closed() -> None:
    assert close(heard_quarters(*quarters(0.25, 0.5, 0.75, 1.0, voiced=True)), 1.0, QUARTER)[1] == Kept(
        pcm=b"\x01\x00" * 4
    )


def test_exactly_the_shortest_voice_is_an_utterance() -> None:
    state = heard_quarters(quarter(voiced=True, at=0.25, pcm=b"a"), quarter(voiced=True, at=0.5, pcm=b"b"))
    assert close(state, 2.0, QUARTER)[1] == Kept(pcm=b"ab")


def test_closing_an_utterance_empties_it() -> None:
    state = heard_quarters(quarter(voiced=True, at=0.25), quarter(voiced=True, at=0.5))
    assert close(state, 2.0, QUARTER)[0].utterance == ()


WIDE_WINDOW = UtteranceRules(silence=0.8, barge_in=0.5, barge_window=5.0)


def test_the_voice_of_a_closed_utterance_no_longer_counts_towards_an_interruption() -> None:
    state, now = listen((VOICE, 30), (SILENCE, 45), rules=WIDE_WINDOW)
    assert not is_speaking(close(state, now, WIDE_WINDOW)[0], WIDE_WINDOW)


TURNS = UtteranceRules(silence=0.8, shortest_voice=0.2, short_pause=0.2)


def awaits_check(*runs: tuple[bool, int], rules: UtteranceRules = TURNS) -> bool:
    state, now = listen(*runs, rules=rules)
    return needs_turn_check(state, now, rules)


def test_no_turn_check_while_the_speaker_talks() -> None:
    assert not awaits_check((VOICE, 50))


def test_a_short_pause_calls_for_a_turn_check() -> None:
    assert awaits_check((VOICE, 50), (SILENCE, 11))


def test_a_pause_shorter_than_the_short_pause_calls_for_no_turn_check() -> None:
    assert not awaits_check((VOICE, 50), (SILENCE, 9))


def test_without_a_short_pause_no_turn_check_is_ever_called_for() -> None:
    assert not awaits_check((VOICE, 50), (SILENCE, 30), rules=RULES)


def test_silence_alone_calls_for_no_turn_check() -> None:
    assert not awaits_check((SILENCE, 30))


def test_a_pause_is_checked_only_once() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 11), rules=TURNS)
    assert not needs_turn_check(turn_checked(state), now + 0.1, TURNS)


def test_a_new_pause_after_more_voice_is_checked_again() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 11), rules=TURNS)
    resumed = hear(
        hear(turn_checked(state), frame(voiced=True, at=now + PACKET), TURNS), frame(voiced=False, at=now + 0.3), TURNS
    )
    assert needs_turn_check(resumed, now + 0.3, TURNS)


def test_a_finished_turn_closes_the_utterance_after_a_short_pause() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 11), rules=TURNS)
    assert close(state, now, TURNS, finished=True)[1] is not None


def test_an_unfinished_turn_keeps_the_utterance_open_before_the_silence() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 11), rules=TURNS)
    assert close(state, now, TURNS, finished=False)[1] is None


def test_a_finished_turn_without_an_utterance_closes_nothing() -> None:
    state, now = listen((SILENCE, 20), rules=TURNS)
    assert close(state, now, TURNS, finished=True)[1] is None
