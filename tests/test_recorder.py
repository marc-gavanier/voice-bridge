import time
from pathlib import Path

from voice_bridge.recorder import lost_packets, next_sequence, wav_path


def test_no_packet_lost_on_the_first_chunk():
    assert lost_packets(None, 40) == 0


def test_no_packet_lost_when_the_expected_one_arrives():
    assert lost_packets(42, 42) == 0


def test_counts_the_packets_skipped_by_the_sequence():
    assert lost_packets(42, 46) == 4


def test_a_late_packet_is_not_counted_as_lost():
    assert lost_packets(42, 40) == 0


def test_next_sequence_advances_by_ten_millisecond_frames():
    assert next_sequence(40, 0.02) == 42


def test_wav_is_named_after_the_day_and_time_it_started():
    start = time.mktime((2026, 11, 8, 17, 55, 57, 0, 0, -1))
    assert wav_path(Path("logs/enregistreur"), start) == Path("logs/enregistreur/2026-11-08/175557.wav")
