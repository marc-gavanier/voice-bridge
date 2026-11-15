import numpy as np
import pytest

from voice_bridge.libraries.audio.pcm import duration
from voice_bridge.libraries.audio.tempo import pace, stretch

RATE = 24000


def tone(frequency: float, seconds: float) -> bytes:
    times = np.arange(round(RATE * seconds)) / RATE
    return (np.sin(2 * np.pi * frequency * times) * 10000).astype(np.int16).tobytes()


def dominant_frequency(pcm: bytes) -> float:
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    return int(np.argmax(spectrum)) * RATE / samples.size


def test_the_natural_pace_keeps_the_audio_as_it_is() -> None:
    assert stretch(tone(440, 1.0), RATE, 1.0) == tone(440, 1.0)


def test_no_audio_stays_no_audio() -> None:
    assert stretch(b"", RATE, 1.2) == b""


def test_a_faster_pace_shortens_the_audio() -> None:
    assert duration(stretch(tone(440, 1.2), RATE, 1.2), RATE) == pytest.approx(1.0, abs=0.05)


def test_a_slower_pace_lengthens_the_audio() -> None:
    assert duration(stretch(tone(440, 1.0), RATE, 0.5), RATE) == pytest.approx(2.0, abs=0.05)


def test_a_faster_pace_keeps_the_pitch() -> None:
    assert dominant_frequency(stretch(tone(440, 2.0), RATE, 1.5)) == pytest.approx(440, abs=5)


def paced_in_pieces(pcm: bytes, factor: float, piece: float) -> list[bytes]:
    paced = pace(RATE, factor)
    size = round(RATE * piece) * 2
    return [*(paced.push(pcm[start : start + size]) for start in range(0, len(pcm), size)), paced.end()]


def test_the_first_piece_is_paced_before_the_rest_arrives() -> None:
    assert duration(paced_in_pieces(tone(440, 2.0), 1.2, 0.4)[0], RATE) >= 0.25


def test_audio_paced_in_pieces_lasts_as_long_as_audio_paced_whole() -> None:
    pieces = paced_in_pieces(tone(440, 2.0), 1.2, 0.4)
    assert duration(b"".join(pieces), RATE) == pytest.approx(
        duration(stretch(tone(440, 2.0), RATE, 1.2), RATE), abs=0.05
    )


def test_the_natural_pace_lets_each_piece_through_as_it_is() -> None:
    assert paced_in_pieces(tone(440, 1.0), 1.0, 0.5) == [tone(440, 1.0)[:24000], tone(440, 1.0)[24000:], b""]


def test_a_pace_fed_no_audio_gives_no_audio() -> None:
    assert paced_in_pieces(b"", 1.2, 0.4) == [b""]
