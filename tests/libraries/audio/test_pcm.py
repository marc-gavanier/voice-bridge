import numpy as np
import pytest

from voice_bridge.libraries.audio.pcm import boost, duration, from_float, level, ramp, resample, to_float


def pcm_of(*values: int) -> bytes:
    return np.array(values, dtype=np.int16).tobytes()


def test_to_float_scales_samples_to_unit_range() -> None:
    assert to_float(pcm_of(16384, -32768)).tolist() == [0.5, -1.0]


def test_from_float_scales_unit_range_to_samples() -> None:
    assert from_float(np.array([0.5, -1.0], dtype=np.float32)) == pcm_of(16384, -32767)


def test_from_float_clips_samples_out_of_range() -> None:
    assert from_float(np.array([2.0, -2.0], dtype=np.float32)) == pcm_of(32767, -32767)


def test_level_of_silence_is_zero() -> None:
    assert level(pcm_of(0, 0, 0, 0)) == 0.0


def test_level_is_the_root_mean_square_of_the_samples() -> None:
    assert level(pcm_of(300, -300, 400, -400)) == pytest.approx(353.55, abs=0.01)


def test_level_of_nothing_is_zero() -> None:
    assert level(b"") == 0.0


def test_boost_raises_quiet_samples() -> None:
    assert level(boost(pcm_of(1000), gain=2.5)) > 2400


def test_boost_never_clips_loud_samples() -> None:
    assert boost(pcm_of(30000, -30000), gain=2.5) == pcm_of(32100, -32100)


def test_boost_keeps_silence() -> None:
    assert boost(pcm_of(0, 0), gain=2.5) == pcm_of(0, 0)


def test_resample_divides_the_sample_count_by_the_rate_ratio() -> None:
    assert len(resample(bytes(48000 * 2), from_rate=48000, to_rate=16000)) == 16000 * 2


def test_resample_keeps_audio_at_the_same_rate() -> None:
    assert resample(pcm_of(1, 2, 3), from_rate=48000, to_rate=48000) == pcm_of(1, 2, 3)


def test_duration_counts_seconds_of_mono_16_bit_audio() -> None:
    assert duration(bytes(96000), rate=48000) == 1.0


def test_a_ramp_up_starts_silent_and_ends_whole() -> None:
    assert to_float(ramp(pcm_of(16384, 16384, 16384), 0.0, 1.0)).tolist() == [0.0, 0.25, 0.5]


def test_a_ramp_down_ends_silent() -> None:
    assert to_float(ramp(pcm_of(16384, 16384, 16384), 1.0, 0.0)).tolist() == [0.5, 0.25, 0.0]


def test_a_ramp_of_nothing_is_nothing() -> None:
    assert ramp(b"", 0.0, 1.0) == b""
