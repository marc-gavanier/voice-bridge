from datetime import datetime
from pathlib import PurePath

import pytest

from voice_bridge.features.recording.domain.take import Heard, begin, extend, file_name, is_over, summary

TWENTY_MS = bytes(1920)


def heard(frame_number: int, at: float) -> Heard:
    return Heard(pcm=TWENTY_MS, at=at, frame_number=frame_number, duration=0.02)


def test_nothing_is_lost_on_the_first_packet() -> None:
    assert begin(heard(0, 1.0)).lost == 0.0


def test_nothing_is_lost_when_the_expected_packet_arrives() -> None:
    assert extend(begin(heard(0, 1.0)), heard(2, 1.02)).lost == 0.0


def test_the_audio_skipped_by_the_frame_number_is_lost() -> None:
    assert extend(begin(heard(0, 1.0)), heard(6, 1.02)).lost == pytest.approx(0.04)


def test_a_late_packet_is_not_counted_as_lost() -> None:
    assert extend(begin(heard(4, 1.0)), heard(2, 1.02)).lost == 0.0


def test_the_longest_gap_between_packets_is_kept() -> None:
    assert extend(extend(begin(heard(0, 1.0)), heard(2, 1.3)), heard(4, 1.32)).longest_gap == pytest.approx(0.3)


def test_a_take_is_over_after_a_long_silence() -> None:
    assert is_over(begin(heard(0, 1.0)), now=3.0, silence=1.5)


def test_a_take_goes_on_during_a_short_silence() -> None:
    assert not is_over(begin(heard(0, 1.0)), now=2.0, silence=1.5)


def test_a_take_is_named_after_the_day_and_time_it_started() -> None:
    start = datetime(2026, 11, 10, 7, 5, 9).astimezone().timestamp()
    assert file_name(begin(heard(0, start))) == PurePath("2026-11-10", "070509.wav")


def test_the_summary_tells_the_length_packets_losses_and_longest_gap() -> None:
    take = extend(begin(heard(0, 1.0)), heard(6, 1.25))
    assert summary(take, rate=48000) == "0.0s, 2 packets, 40 ms lost, longest gap 250 ms"
