import faulthandler
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

logger = logging.getLogger(__name__)


def crash_file_of(log_file: Path) -> Path:
    return log_file.with_suffix(".crash")


def _report_previous(crash_file: Path) -> None:
    dump = crash_file.read_text(encoding="utf-8").strip() if crash_file.exists() else ""
    if dump:
        logger.error("the previous run crashed outside Python:\n%s", dump)


@contextmanager
def watching_crashes(crash_file: Path) -> Generator[None]:
    _report_previous(crash_file)
    with crash_file.open("w", encoding="utf-8") as stream:
        faulthandler.enable(stream, all_threads=True)
        try:
            yield
        finally:
            faulthandler.disable()
