import gzip
import logging
from pathlib import Path

from voice_bridge.libraries.rotation.daily import DailyFile


def logged(handler: DailyFile, line: str) -> None:
    handler.emit(logging.makeLogRecord({"msg": line}))


def rolled(path: Path, *, kept: int, before: str, after: str) -> None:
    handler = DailyFile(path, kept=kept)
    logged(handler, before)
    handler.doRollover()
    logged(handler, after)
    handler.close()


def old_days(path: Path, *days: str) -> None:
    for day in days:
        _ = path.with_name(f"{path.name}.{day}.gz").write_bytes(gzip.compress(day.encode()))


def compressed(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.name}.*.gz"))


def test_a_line_is_written_to_the_file(tmp_path: Path) -> None:
    handler = DailyFile(tmp_path / "voice-bridge.log")
    logged(handler, "a line")
    handler.close()
    assert (tmp_path / "voice-bridge.log").read_text(encoding="utf-8") == "a line\n"


def test_the_file_of_a_day_is_compressed_when_the_next_day_starts(tmp_path: Path) -> None:
    rolled(tmp_path / "voice-bridge.log", kept=0, before="yesterday", after="today")
    assert [gzip.decompress(path.read_bytes()) for path in compressed(tmp_path / "voice-bridge.log")] == [
        b"yesterday\n"
    ]


def test_the_next_day_starts_a_new_file(tmp_path: Path) -> None:
    rolled(tmp_path / "voice-bridge.log", kept=0, before="yesterday", after="today")
    assert (tmp_path / "voice-bridge.log").read_text(encoding="utf-8") == "today\n"


def test_the_compressed_file_is_named_after_its_day(tmp_path: Path) -> None:
    rolled(tmp_path / "voice-bridge.log", kept=0, before="yesterday", after="today")
    assert [path.name for path in compressed(tmp_path / "voice-bridge.log")] == [
        path.name for path in tmp_path.glob("voice-bridge.log.????-??-??.gz")
    ]


def test_only_the_days_kept_remain(tmp_path: Path) -> None:
    old_days(tmp_path / "traces.jsonl", "2020-01-01", "2020-01-02", "2020-01-03")
    rolled(tmp_path / "traces.jsonl", kept=2, before="yesterday", after="today")
    assert len(compressed(tmp_path / "traces.jsonl")) == 2


def test_the_oldest_days_go_first(tmp_path: Path) -> None:
    old_days(tmp_path / "traces.jsonl", "2020-01-01", "2020-01-02", "2020-01-03")
    rolled(tmp_path / "traces.jsonl", kept=2, before="yesterday", after="today")
    assert (tmp_path / "traces.jsonl.2020-01-03.gz").exists()


def test_keeping_no_count_keeps_every_day(tmp_path: Path) -> None:
    old_days(tmp_path / "traces.jsonl", "2020-01-01", "2020-01-02", "2020-01-03")
    rolled(tmp_path / "traces.jsonl", kept=0, before="yesterday", after="today")
    assert len(compressed(tmp_path / "traces.jsonl")) == 4


def test_other_files_of_the_directory_are_left_alone(tmp_path: Path) -> None:
    old_days(tmp_path / "traces.jsonl", "2020-01-01", "2020-01-02")
    old_days(tmp_path / "metrics.jsonl", "2020-01-01")
    rolled(tmp_path / "traces.jsonl", kept=1, before="yesterday", after="today")
    assert (tmp_path / "metrics.jsonl.2020-01-01.gz").exists()
