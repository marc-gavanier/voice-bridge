import io
import wave

import numpy as np
import pytest

from voice_bridge.libraries.audio.wav import decode, encode


def raw_wav(frames: bytes, *, width: int, rate: int = 48000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return buffer.getvalue()


def wav_of(samples: list[int], *, rate: int = 48000, channels: int = 1, dtype: type[np.integer] = np.int16) -> bytes:
    return raw_wav(
        np.array(samples, dtype=dtype).tobytes(), width=np.dtype(dtype).itemsize, rate=rate, channels=channels
    )


def pcm_of(*values: int) -> bytes:
    return np.array(values, dtype=np.int16).tobytes()


def test_decode_keeps_mono_16_bit_audio_at_the_target_rate() -> None:
    assert decode(wav_of([100, -200, 300]), rate=48000) == pcm_of(100, -200, 300)


def test_decode_mixes_stereo_down_to_mono() -> None:
    assert decode(wav_of([100, 300, -100, -300], channels=2), rate=48000) == pcm_of(200, -200)


def test_decode_converts_32_bit_samples_to_16_bit() -> None:
    assert decode(wav_of([65536 * 100], dtype=np.int32), rate=48000) == pcm_of(100)


def test_decode_converts_8_bit_samples_to_16_bit() -> None:
    assert decode(wav_of([192], dtype=np.uint8), rate=48000) == pcm_of(16384)


def test_decode_resamples_to_the_target_rate() -> None:
    assert len(decode(wav_of([0] * 24000, rate=24000), rate=48000)) == 48000 * 2


def test_decode_refuses_24_bit_samples() -> None:
    with pytest.raises(ValueError, match="3-byte samples"):
        _ = decode(raw_wav(bytes(6), width=3), rate=48000)


def test_encode_produces_a_wav_that_decodes_back() -> None:
    assert decode(encode(pcm_of(1, -2, 3), rate=48000), rate=48000) == pcm_of(1, -2, 3)
