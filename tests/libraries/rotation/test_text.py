import gzip
from pathlib import Path

from voice_bridge.libraries.rotation.daily import DailyFile
from voice_bridge.libraries.rotation.text import RotatingText


def opened(path: Path) -> RotatingText:
    return RotatingText(DailyFile(path, kept=2))


def written(path: Path, *lines: str) -> None:
    stream = opened(path)
    _ = [stream.write(line) for line in lines]
    stream.flush()
    stream.close()


def written_across_midnight(path: Path, before: str, after: str) -> None:
    handler = DailyFile(path, kept=2)
    stream = RotatingText(handler)
    _ = stream.write(before)
    handler.rolloverAt = 0
    _ = stream.write(after)
    stream.close()


def test_lines_written_are_kept_in_the_file(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "one\n", "two\n")
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "one\ntwo\n"


def test_a_line_is_written_as_it_is(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", '{"text":"100 %s %(name)s"}\n')
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == '{"text":"100 %s %(name)s"}\n'


def test_a_write_tells_how_many_characters_it_wrote(tmp_path: Path) -> None:
    stream = opened(tmp_path / "traces.jsonl")
    count = stream.write("été\n")
    stream.close()
    assert count == 4


def test_a_line_written_after_midnight_starts_a_new_file(tmp_path: Path) -> None:
    written_across_midnight(tmp_path / "traces.jsonl", "yesterday\n", "today\n")
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "today\n"


def test_the_lines_of_the_day_before_are_kept_compressed(tmp_path: Path) -> None:
    written_across_midnight(tmp_path / "traces.jsonl", "yesterday\n", "today\n")
    assert [gzip.decompress(path.read_bytes()) for path in tmp_path.glob("traces.jsonl.*.gz")] == [b"yesterday\n"]


def test_a_new_stream_appends_to_the_file(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "before\n")
    written(tmp_path / "traces.jsonl", "after\n")
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "before\nafter\n"


def test_an_open_stream_is_not_closed(tmp_path: Path) -> None:
    stream = opened(tmp_path / "traces.jsonl")
    closed = stream.closed
    stream.close()
    assert not closed


def test_a_closed_stream_says_so(tmp_path: Path) -> None:
    stream = opened(tmp_path / "traces.jsonl")
    stream.close()
    assert stream.closed


def test_a_stream_is_writable(tmp_path: Path) -> None:
    stream = opened(tmp_path / "traces.jsonl")
    stream.close()
    assert stream.writable()
