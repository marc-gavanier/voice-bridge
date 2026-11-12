import wave
from itertools import accumulate
from pathlib import Path

import numpy as np
from faster_whisper.vad import get_vad_model

from voice_bridge.features.hearing.implementation.silero import Silero, Voicing, is_voiced, listen
from voice_bridge.libraries.audio.pcm import from_float

RATE = 48000
PACKET_BYTES = 960 * 2
SPEECH = Path(__file__).parents[3] / "fixtures" / "speech.wav"
QUIET_ENOUGH = Voicing(volume_threshold=0.0, probability=0.5)


def packets(pcm: bytes) -> list[bytes]:
    return [pcm[start : start + PACKET_BYTES] for start in range(0, len(pcm) - PACKET_BYTES + 1, PACKET_BYTES)]


def states(pcm: bytes) -> list[Silero]:
    session = get_vad_model().session
    return list(accumulate(packets(pcm), lambda state, packet: listen(session, state, packet, RATE), initial=Silero()))[
        1:
    ]


def decisions(pcm: bytes, voicing: Voicing = QUIET_ENOUGH) -> list[bool]:
    return [is_voiced(state, packet, voicing) for state, packet in zip(states(pcm), packets(pcm), strict=True)]


def speech() -> bytes:
    with wave.open(str(SPEECH), "rb") as recording:
        return recording.readframes(recording.getnframes())


def white_noise() -> bytes:
    return from_float(np.random.default_rng(1).normal(0, 0.3, RATE * 3).astype(np.float32))


def engine_hum() -> bytes:
    time = np.arange(RATE * 3) / RATE
    sawtooth = 2 * ((time * 90) % 1) - 1
    rumble = np.random.default_rng(2).normal(0, 0.1, time.size)
    return from_float((0.5 * sawtooth + rumble).astype(np.float32))


def test_silence_is_not_voice() -> None:
    assert not any(decisions(bytes(RATE * 2 * 2)))


def test_white_noise_is_not_voice() -> None:
    assert not any(decisions(white_noise()))


def test_engine_hum_never_adds_up_to_half_a_second_of_voice() -> None:
    assert sum(decisions(engine_hum())) * 0.02 < 0.5


def test_speech_is_voice() -> None:
    assert any(decisions(speech()))


def test_quiet_speech_is_not_voice() -> None:
    assert not any(decisions(speech(), Voicing(volume_threshold=1e9, probability=0.5)))
