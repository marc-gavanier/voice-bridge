from pathlib import Path

from voice_bridge.libraries.rotation.text import RotatingText


def written(path: Path, *lines: str, largest: int = 1000) -> None:
    stream = RotatingText(path, largest=largest, kept=2)
    _ = [stream.write(line) for line in lines]
    stream.flush()
    stream.close()


def test_lines_written_are_kept_in_the_file(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "one\n", "two\n")
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "one\ntwo\n"


def test_a_line_is_written_as_it_is(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", '{"text":"100 %s %(name)s"}\n')
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == '{"text":"100 %s %(name)s"}\n'


def test_a_write_tells_how_many_characters_it_wrote(tmp_path: Path) -> None:
    stream = RotatingText(tmp_path / "traces.jsonl", largest=1000, kept=2)
    count = stream.write("été\n")
    stream.close()
    assert count == 4


def test_a_line_that_would_pass_the_largest_size_starts_a_new_file(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "first\n", "second\n", largest=10)
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "second\n"


def test_the_full_file_is_kept_beside_the_new_one(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "first\n", "second\n", largest=10)
    assert (tmp_path / "traces.jsonl.1").read_text(encoding="utf-8") == "first\n"


def test_only_the_kept_number_of_full_files_remain(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "first\n", "second\n", "third\n", "fourth\n", largest=10)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["traces.jsonl", "traces.jsonl.1", "traces.jsonl.2"]


def test_a_new_stream_appends_to_the_file(tmp_path: Path) -> None:
    written(tmp_path / "traces.jsonl", "before\n")
    written(tmp_path / "traces.jsonl", "after\n")
    assert (tmp_path / "traces.jsonl").read_text(encoding="utf-8") == "before\nafter\n"


def test_an_open_stream_is_not_closed(tmp_path: Path) -> None:
    stream = RotatingText(tmp_path / "traces.jsonl", largest=1000, kept=2)
    closed = stream.closed
    stream.close()
    assert not closed


def test_a_closed_stream_says_so(tmp_path: Path) -> None:
    stream = RotatingText(tmp_path / "traces.jsonl", largest=1000, kept=2)
    stream.close()
    assert stream.closed


def test_a_stream_is_writable(tmp_path: Path) -> None:
    stream = RotatingText(tmp_path / "traces.jsonl", largest=1000, kept=2)
    stream.close()
    assert stream.writable()
