import wave
from pathlib import Path

import numpy as np

from voice_bridge.speech import all_of
from voice_bridge.vad import VoiceActivity, load_vad_model

RATE = 48000
PACKET_SAMPLES = 960
FIXTURES = Path(__file__).parent / "fixtures"


def packets(pcm):
    size = PACKET_SAMPLES * 2
    return [pcm[i:i + size] for i in range(0, len(pcm) - size + 1, size)]


def decisions(pcm):
    activity = VoiceActivity(load_vad_model())
    return [activity.is_voice(packet) for packet in packets(pcm)]


def to_pcm(samples):
    return (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()


def speech():
    with wave.open(str(FIXTURES / "parole.wav")) as recording:
        return recording.readframes(recording.getnframes())


def white_noise():
    return to_pcm(np.random.default_rng(1).normal(0, 0.3, RATE * 3))


def engine_hum():
    t = np.arange(RATE * 3) / RATE
    sawtooth = 2 * ((t * 90) % 1) - 1
    rumble = np.random.default_rng(2).normal(0, 0.1, t.size)
    return to_pcm(0.5 * sawtooth + rumble)


def test_silence_is_not_voice():
    assert not any(decisions(bytes(RATE * 2 * 2)))


def test_white_noise_is_not_voice():
    assert not any(decisions(white_noise()))


def test_engine_hum_never_adds_up_to_half_a_second_of_voice():
    assert sum(decisions(engine_hum())) * PACKET_SAMPLES / RATE < 0.5


def test_speech_is_voice():
    assert any(decisions(speech()))


def test_voice_model_keeps_listening_when_another_check_refuses():
    activity = VoiceActivity(load_vad_model())
    check = all_of(lambda pcm: False, activity.is_voice)
    list(map(check, packets(speech())))
    assert activity.probability > 0
