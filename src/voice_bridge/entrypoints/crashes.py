import faulthandler
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

import anyio

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator
    from pathlib import Path

    from anyio.abc import TaskStatus

logger = logging.getLogger(__name__)

BEATS_PER_WAIT = 4


@dataclass(frozen=True, slots=True, kw_only=True)
class Watch:
    file: Path
    stream: TextIO


def crash_file_of(log_file: Path) -> Path:
    return log_file.with_suffix(".crash")


def _dump_of(watch: Watch) -> str:
    return watch.file.read_text(encoding="utf-8").strip() if watch.file.exists() else ""


def _empty(watch: Watch) -> None:
    descriptor = watch.stream.fileno()
    os.ftruncate(descriptor, 0)
    _ = os.lseek(descriptor, 0, os.SEEK_SET)


def _report_previous(crash_file: Path) -> None:
    dump = crash_file.read_text(encoding="utf-8").strip() if crash_file.exists() else ""
    if dump:
        logger.error("the previous run crashed outside Python:\n%s", dump)


@contextmanager
def watching_crashes(crash_file: Path) -> Generator[Watch]:
    _report_previous(crash_file)
    with crash_file.open("w", encoding="utf-8") as stream:
        faulthandler.enable(stream, all_threads=True)
        try:
            yield Watch(file=crash_file, stream=stream)
        finally:
            faulthandler.cancel_dump_traceback_later()
            faulthandler.disable()


def _report_hang(watch: Watch, after: float) -> None:
    dump = _dump_of(watch)
    if dump:
        logger.warning("the bridge was blocked for over %g s:\n%s", after, dump)
        _empty(watch)


async def _beat(watch: Watch, after: float, *, task_status: TaskStatus[None]) -> None:
    faulthandler.dump_traceback_later(after, file=watch.stream)
    task_status.started()
    while True:
        await anyio.sleep(after / BEATS_PER_WAIT)
        _report_hang(watch, after)
        faulthandler.dump_traceback_later(after, file=watch.stream)


async def watching_hangs(watch: Watch, after: float, run: Callable[[], Awaitable[None]]) -> None:
    async with anyio.create_task_group() as tasks:
        await tasks.start(_beat, watch, after)
        await run()
        tasks.cancel_scope.cancel()
    faulthandler.cancel_dump_traceback_later()
