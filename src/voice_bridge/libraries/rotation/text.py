import logging
from typing import TYPE_CHECKING, TextIO, override

if TYPE_CHECKING:
    from logging import FileHandler


class RotatingText(TextIO):
    def __init__(self, handler: FileHandler) -> None:
        self._handler: FileHandler = handler
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
