import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import reduce
from pathlib import Path

import anyio
import pytest

from voice_bridge.features.hearing.abilities.listen.domain.heard import (
    Heard,
    Speaking,
    Turn,
    TurnChecked,
    Utterance,
    VoiceStarted,
)
from voice_bridge.features.hearing.abilities.listen.domain.ports import VoiceDetector
from voice_bridge.features.hearing.abilities.listen.domain.voicing import Voicing
from voice_bridge.features.hearing.abilities.listen.implementation.listen import Ears, advance, listen
from voice_bridge.features.hearing.domain.utterance import Dismissed, Listening, UtteranceRules
from voice_bridge.libraries.mumble.audio import Packet

RATE = 48000
PACKET_BYTES = 1920
SPEECH = Path(__file__).parents[5] / "fixtures" / "speech.wav"
ANY_VOLUME = Voicing(volume_threshold=0.0, probability=0.5)


def scoring(probability: float) -> VoiceDetector:
    return lambda _: probability


@dataclass
class RecordingDetector:
    scored: list[bytes] = field(default_factory=list)

    def __call__(self, pcm: bytes, /) -> float:
        self.scored.append(pcm)
        return 1.0


def ears(detector: VoiceDetector, voicing: Voicing = ANY_VOLUME, turn: Turn | None = None) -> Ears:
    rules = UtteranceRules() if turn is None else UtteranceRules(short_pause=0.2)
    return Ears(detector=detector, voicing=voicing, rules=rules, rate=RATE, turn=turn)


EARS = ears(scoring(1.0))
DEAF_EARS = ears(scoring(0.0))

type Tick = tuple[Packet | None, float]


def speech_ticks() -> list[Tick]:
    with wave.open(str(SPEECH), "rb") as recording:
        pcm = recording.readframes(recording.getnframes())
    starts = range(0, len(pcm) - PACKET_BYTES + 1, PACKET_BYTES)
    return [
        (Packet(pcm=pcm[start : start + PACKET_BYTES], at=index * 0.02, frame_number=index * 2), index * 0.02)
        for index, start in enumerate(starts)
    ]


def packet_audio(ticks: list[Tick]) -> list[bytes]:
    return [packet.pcm for packet, _ in ticks if packet is not None]


def silence_ticks(count: int) -> list[Tick]:
    return [
        (Packet(pcm=bytes(PACKET_BYTES), at=index * 0.02, frame_number=index), index * 0.02) for index in range(count)
    ]


EARS_TOO_LOUD_TO_REACH = ears(scoring(1.0), Voicing(volume_threshold=1e9, probability=0.5))


def heard(ticks: list[Tick], ears: Ears = EARS) -> tuple[Heard, ...]:
    def step(result: tuple[Listening, tuple[Heard, ...]], tick: Tick) -> tuple[Listening, tuple[Heard, ...]]:
        state, reported = advance(ears, result[0], tick[0], tick[1])
        return state, (*result[1], *reported)

    return reduce(step, ticks, (Listening(), ()))[1]


def test_speech_is_reported_first_as_starting_then_as_speaking() -> None:
    assert [type(each) for each in heard(speech_ticks())[:2]] == [VoiceStarted, Speaking]


def test_speech_starts_only_once_per_utterance() -> None:
    assert sum(isinstance(each, VoiceStarted) for each in heard(speech_ticks())) == 1


def test_speech_followed_by_a_pause_is_an_utterance() -> None:
    assert isinstance(heard([*speech_ticks(), (None, 10.0)])[-1], Utterance)


def test_speech_quieter_than_the_volume_threshold_is_never_reported() -> None:
    assert heard([*speech_ticks(), (None, 10.0)], EARS_TOO_LOUD_TO_REACH) == ()


def test_sound_the_detector_does_not_take_for_voice_is_never_reported() -> None:
    assert heard([*speech_ticks(), (None, 10.0)], DEAF_EARS) == ()


def test_sound_scored_below_the_probability_is_never_reported() -> None:
    assert heard([*speech_ticks(), (None, 10.0)], ears(scoring(0.49))) == ()


def test_the_detector_scores_the_audio_of_each_packet() -> None:
    detector = RecordingDetector()
    _ = heard(speech_ticks(), ears(detector))
    assert detector.scored == packet_audio(speech_ticks())


def test_a_pause_alone_is_never_reported() -> None:
    assert advance(EARS, Listening(), None, 1.0)[1] == ()


async def ticks_of(ticks: list[Tick]) -> AsyncIterator[Packet | None]:
    for tick, _ in ticks:
        yield tick


@pytest.mark.anyio
async def test_listening_reports_what_it_hears() -> None:
    sent, received = anyio.create_memory_object_stream[Heard](1000)
    async with sent, received:
        await listen(EARS, ticks_of(speech_ticks()), sent.send, clock=lambda: 0.0)
        first = received.receive_nowait()
    assert isinstance(first, VoiceStarted)


def test_a_sound_too_short_to_be_an_utterance_is_reported_as_dismissed() -> None:
    assert [type(each) for each in heard([*silence_ticks(5), (None, 10.0)])] == [
        VoiceStarted,
        Dismissed,
    ]


def ears_judging(probability: float) -> Ears:
    return ears(scoring(1.0), turn=Turn(judge=lambda _: probability, threshold=0.5))


def after_a_short_pause(ears: Ears) -> tuple[Heard, ...]:
    return heard([*silence_ticks(50), (None, 1.25)], ears)


def test_a_finished_turn_ends_the_utterance_after_a_short_pause() -> None:
    assert [type(each) for each in after_a_short_pause(ears_judging(0.9))[-2:]] == [TurnChecked, Utterance]


def test_an_unfinished_turn_keeps_listening_after_a_short_pause() -> None:
    assert isinstance(after_a_short_pause(ears_judging(0.1))[-1], TurnChecked)


def last_check(heard_so_far: tuple[Heard, ...]) -> TurnChecked:
    return next(each for each in reversed(heard_so_far) if isinstance(each, TurnChecked))


def test_the_turn_check_reports_the_probability() -> None:
    assert last_check(after_a_short_pause(ears_judging(0.9))).probability == 0.9


def test_the_turn_check_reports_how_long_the_pause_lasted() -> None:
    assert last_check(after_a_short_pause(ears_judging(0.9))).pause == pytest.approx(0.27)


def test_without_a_turn_judge_no_turn_is_checked() -> None:
    assert TurnChecked not in [type(each) for each in after_a_short_pause(EARS)]
