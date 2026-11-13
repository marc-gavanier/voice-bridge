import faulthandler
import logging
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import anyio
import pytest

from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs

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


WAIT = 0.1


def block(seconds: float) -> None:
    time.sleep(seconds)


def warnings_of(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage().split("\n")[0] for record in caplog.records if record.levelno == logging.WARNING]


async def run_watched(crash_file: Path, run: Callable[[], Awaitable[None]]) -> None:
    with watching_crashes(crash_file) as watch:
        await watching_hangs(watch, WAIT, run)


async def blocked_then_resumed() -> None:
    block(WAIT * 3)
    await anyio.sleep(WAIT)


async def smooth() -> None:
    await anyio.sleep(WAIT * 3)


@pytest.mark.anyio
async def test_a_blocked_loop_is_logged_as_a_warning_once_it_resumes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    await run_watched(tmp_path / "voice-bridge.crash", blocked_then_resumed)
    assert warnings_of(caplog) == ["the bridge was blocked for over 0.1 s:"]


@pytest.mark.anyio
async def test_the_stack_of_a_blocked_loop_is_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    await run_watched(tmp_path / "voice-bridge.crash", blocked_then_resumed)
    assert "in block" in caplog.text


@pytest.mark.anyio
async def test_a_logged_hang_leaves_the_crash_file_empty(tmp_path: Path) -> None:
    await run_watched(tmp_path / "voice-bridge.crash", blocked_then_resumed)
    assert (tmp_path / "voice-bridge.crash").read_text(encoding="utf-8") == ""


@pytest.mark.anyio
async def test_a_loop_that_keeps_turning_logs_no_hang(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    await run_watched(tmp_path / "voice-bridge.crash", smooth)
    assert warnings_of(caplog) == []
