import logging
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, TextIO, override

if TYPE_CHECKING:
    from pathlib import Path


class RotatingText(TextIO):
    def __init__(self, path: Path, *, largest: int, kept: int) -> None:
        self._handler: RotatingFileHandler = RotatingFileHandler(
            path, maxBytes=largest, backupCount=kept, encoding="utf-8"
        )
        self._handler.terminator = ""
        self._closed: bool = False

    @override
    def write(self, s: str, /) -> int:
        self._handler.emit(logging.makeLogRecord({"msg": s}))
        return len(s)

    @override
    def flush(self) -> None:
        self._handler.flush()

    @override
    def writable(self) -> bool:
        return True

    @property
    @override
    def closed(self) -> bool:
        return self._closed

    @override
    def close(self) -> None:
        self._handler.close()
        self._closed = True
