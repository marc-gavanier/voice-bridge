from functools import reduce

from voice_bridge.features.hearing.abilities.listen.domain.heard import (
    Heard,
    Speaking,
    Turn,
    TurnChecked,
    Utterance,
    VoiceStarted,
    heard_frame,
    paused,
)
from voice_bridge.features.hearing.abilities.listen.domain.ports import Judge
from voice_bridge.features.hearing.domain.utterance import Dismissed, Frame, Listening, UtteranceRules

RULES = UtteranceRules()
TURN_RULES = UtteranceRules(short_pause=0.2)

type Result = tuple[Listening, tuple[Heard, ...]]


def voiced(at: float) -> Frame:
    return Frame(pcm=b"v", voiced=True, at=at, duration=0.125)


def silent(at: float) -> Frame:
    return Frame(pcm=b"s", voiced=False, at=at, duration=0.125)


def voice_from_one_second(count: int) -> list[Frame]:
    return [voiced(1.0 + index / 8) for index in range(count)]


def listened(frames: list[Frame], rules: UtteranceRules = RULES, turn: Turn | None = None) -> Result:
    def step(result: Result, frame: Frame) -> Result:
        return heard_frame(result[0], frame, rules, turn)

    return reduce(step, frames, (Listening(), ()))


def judging(probability: float) -> Turn:
    def judge(_audio: bytes) -> float:
        return probability

    return Turn(judge=judge, threshold=0.5)


def finished_only_on(expected: bytes) -> Judge:
    def judge(audio: bytes) -> float:
        return 0.9 if audio == expected else 0.1

    return judge


def paused_after(frames: list[Frame], now: float, turn: Turn | None) -> Result:
    return paused(listened(frames, TURN_RULES, turn)[0], now, TURN_RULES, turn)


def test_the_first_voiced_frame_starts_the_voice() -> None:
    assert listened([voiced(1.0)])[1] == (VoiceStarted(at=1.0),)


def test_the_voice_starts_only_once_per_utterance() -> None:
    assert listened(voice_from_one_second(2))[1] == ()


def test_a_silent_frame_before_any_voice_is_not_reported() -> None:
    assert listened([silent(1.0)])[1] == ()


def test_enough_voice_is_reported_as_speaking() -> None:
    assert listened(voice_from_one_second(5))[1] == (Speaking(at=1.5),)


def test_a_silent_frame_long_after_the_voice_ends_the_utterance() -> None:
    assert listened([*voice_from_one_second(3), silent(2.25)])[1] == (Utterance(pcm=b"vvvs", ended=1.25),)


def test_a_pause_long_after_the_voice_ends_the_utterance() -> None:
    assert paused(listened(voice_from_one_second(3))[0], 2.25, RULES, None)[1] == (Utterance(pcm=b"vvv", ended=1.25),)


def test_a_pause_after_too_little_voice_dismisses_it() -> None:
    assert paused(listened([voiced(1.0)])[0], 2.0, RULES, None)[1] == (Dismissed(voice=0.125, duration=0.125),)


def test_an_ended_utterance_is_forgotten() -> None:
    assert paused(listened(voice_from_one_second(3))[0], 2.25, RULES, None)[0].utterance == ()


def test_a_short_pause_keeps_listening() -> None:
    assert paused(listened(voice_from_one_second(3))[0], 1.75, RULES, None)[1] == ()


def test_a_pause_without_voice_is_not_reported() -> None:
    assert paused(Listening(), 5.0, RULES, None) == (Listening(), ())


def test_a_finished_turn_ends_the_utterance_after_a_short_pause() -> None:
    assert paused_after(voice_from_one_second(3), 1.75, judging(0.9))[1] == (
        TurnChecked(probability=0.9, pause=0.5, finished=True),
        Utterance(pcm=b"vvv", ended=1.25),
    )


def test_a_turn_judged_at_the_threshold_is_unfinished() -> None:
    assert paused_after(voice_from_one_second(3), 1.75, judging(0.5))[1] == (
        TurnChecked(probability=0.5, pause=0.5, finished=False),
    )


def test_an_unfinished_turn_is_remembered() -> None:
    assert paused_after(voice_from_one_second(3), 1.75, judging(0.1))[0].unfinished_at == 1.25


def test_the_turn_is_judged_on_the_audio_of_the_utterance() -> None:
    assert paused_after(voice_from_one_second(3), 1.75, Turn(judge=finished_only_on(b"vvv"), threshold=0.5))[1][
        0
    ] == TurnChecked(probability=0.9, pause=0.5, finished=True)


def test_without_a_turn_judge_no_turn_is_checked() -> None:
    assert paused_after(voice_from_one_second(3), 1.75, None)[1] == ()


def test_a_turn_is_checked_on_a_frame_too() -> None:
    assert listened([*voice_from_one_second(3), silent(1.75)], TURN_RULES, judging(0.9))[1] == (
        TurnChecked(probability=0.9, pause=0.5, finished=True),
        Utterance(pcm=b"vvvs", ended=1.25),
    )
