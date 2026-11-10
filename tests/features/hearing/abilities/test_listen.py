import wave
from collections.abc import AsyncIterator
from functools import reduce
from pathlib import Path

import anyio
import pytest
from faster_whisper.vad import get_vad_model

from voice_bridge.features.hearing.abilities.listen import Ears, Heard, Hearing, Speaking, Utterance, advance, listen
from voice_bridge.features.hearing.domain.utterance import Dismissed, UtteranceRules
from voice_bridge.features.hearing.implementations.silero import Voicing
from voice_bridge.libraries.mumble.audio import Packet

RATE = 48000
PACKET_BYTES = 1920
SPEECH = Path(__file__).parents[3] / "fixtures" / "speech.wav"
EARS = Ears(
    session=get_vad_model().session,
    voicing=Voicing(volume_threshold=0.0, probability=0.5),
    rules=UtteranceRules(),
    rate=RATE,
)

type Tick = tuple[Packet | None, float]


def speech_ticks() -> list[Tick]:
    with wave.open(str(SPEECH), "rb") as recording:
        pcm = recording.readframes(recording.getnframes())
    starts = range(0, len(pcm) - PACKET_BYTES + 1, PACKET_BYTES)
    return [
        (Packet(pcm=pcm[start : start + PACKET_BYTES], at=index * 0.02, frame_number=index * 2), index * 0.02)
        for index, start in enumerate(starts)
    ]


def silence_ticks(count: int) -> list[Tick]:
    return [
        (Packet(pcm=bytes(PACKET_BYTES), at=index * 0.02, frame_number=index), index * 0.02) for index in range(count)
    ]


EARS_FOR_EVERYTHING = Ears(
    session=get_vad_model().session,
    voicing=Voicing(volume_threshold=0.0, probability=0.0),
    rules=UtteranceRules(),
    rate=RATE,
)


def heard(ticks: list[Tick], ears: Ears = EARS) -> tuple[Heard, ...]:
    def step(result: tuple[Hearing, tuple[Heard, ...]], tick: Tick) -> tuple[Hearing, tuple[Heard, ...]]:
        state, reported = advance(ears, result[0], tick[0], tick[1])
        return state, (*result[1], *reported)

    return reduce(step, ticks, (Hearing(), ()))[1]


def test_speech_is_reported_as_speaking() -> None:
    assert isinstance(heard(speech_ticks())[0], Speaking)


def test_speech_followed_by_a_pause_is_an_utterance() -> None:
    assert isinstance(heard([*speech_ticks(), (None, 10.0)])[-1], Utterance)


def test_silence_is_never_reported() -> None:
    assert heard([*silence_ticks(100), (None, 10.0)]) == ()


def test_a_pause_alone_is_never_reported() -> None:
    assert advance(EARS, Hearing(), None, 1.0)[1] == ()


async def ticks_of(ticks: list[Tick]) -> AsyncIterator[Packet | None]:
    for tick, _ in ticks:
        yield tick


@pytest.mark.anyio
async def test_listening_reports_what_it_hears() -> None:
    sent, received = anyio.create_memory_object_stream[Heard](1000)
    async with sent, received:
        await listen(EARS, ticks_of(speech_ticks()), sent.send, clock=lambda: 0.0)
        first = received.receive_nowait()
    assert isinstance(first, Speaking)


def test_a_sound_too_short_to_be_an_utterance_is_reported_as_dismissed() -> None:
    assert heard([*silence_ticks(5), (None, 10.0)], EARS_FOR_EVERYTHING) == (Dismissed(),)
