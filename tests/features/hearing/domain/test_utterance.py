from functools import reduce

from voice_bridge.features.hearing.domain.utterance import (
    Frame,
    Listening,
    UtteranceRules,
    close,
    hear,
    is_speaking,
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


def closed(*runs: tuple[bool, int], rules: UtteranceRules = RULES) -> bytes | None:
    state, now = listen(*runs, rules=rules)
    return close(state, now, rules)[1]


def test_nothing_is_closed_while_the_speaker_talks() -> None:
    assert closed((VOICE, 50)) is None


def test_an_utterance_is_closed_after_a_silence() -> None:
    assert closed((VOICE, 50), (SILENCE, 45)) is not None


def test_the_utterance_holds_all_the_voice() -> None:
    assert len(closed((VOICE, 50), (SILENCE, 45)) or b"") >= 50 * PACKET_BYTES


def test_an_utterance_is_closed_only_once() -> None:
    state, now = listen((VOICE, 50), (SILENCE, 45))
    assert close(close(state, now, RULES)[0], now, RULES)[1] is None


def test_a_short_noise_is_not_an_utterance() -> None:
    assert closed((VOICE, 3), (SILENCE, 45)) is None


def test_silence_alone_is_not_an_utterance() -> None:
    assert closed((SILENCE, 200)) is None


def test_the_utterance_keeps_the_audio_just_before_the_voice() -> None:
    assert len(closed((SILENCE, 20), (VOICE, 50), (SILENCE, 45)) or b"") >= (50 + 45 + 5) * PACKET_BYTES


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
