import faulthandler
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes

DUMP = (
    "Fatal Python error: Segmentation fault\n\n"
    "Current thread 0x00007f (most recent call first):\n"
    '  File "whisper.py", line 1'
)


@pytest.fixture(autouse=True)
def faulthandler_back_to_stderr() -> Iterator[None]:
    yield
    faulthandler.enable()


def errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]


def watched(crash_file: Path) -> bool:
    with watching_crashes(crash_file):
        return faulthandler.is_enabled()


def test_the_crash_file_sits_next_to_the_log() -> None:
    assert crash_file_of(Path("/var/log/voice-bridge/voice-bridge.log")) == Path(
        "/var/log/voice-bridge/voice-bridge.crash"
    )


def test_crashes_are_watched_while_the_bridge_runs(tmp_path: Path) -> None:
    assert watched(tmp_path / "voice-bridge.crash")


def test_crashes_are_no_longer_watched_once_it_stops(tmp_path: Path) -> None:
    _ = watched(tmp_path / "voice-bridge.crash")
    assert not faulthandler.is_enabled()


def test_a_crash_of_the_previous_run_is_logged_as_an_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    crash_file = tmp_path / "voice-bridge.crash"
    _ = crash_file.write_text(DUMP, encoding="utf-8")
    _ = watched(crash_file)
    assert errors(caplog) == [f"the previous run crashed outside Python:\n{DUMP}"]


def test_a_crash_is_logged_only_once(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    crash_file = tmp_path / "voice-bridge.crash"
    _ = crash_file.write_text(DUMP, encoding="utf-8")
    _ = watched(crash_file)
    caplog.clear()
    _ = watched(crash_file)
    assert errors(caplog) == []


def test_a_run_without_crash_logs_no_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _ = watched(tmp_path / "voice-bridge.crash")
    assert errors(caplog) == []
