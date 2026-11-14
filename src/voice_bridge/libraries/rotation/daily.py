import gzip
import shutil
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from os import PathLike


def compressed_name(name: str) -> str:
    return f"{name}.gz"


def compress(source: str, destination: str) -> None:
    with Path(source).open("rb") as plain, gzip.open(destination, "wb") as packed:
        shutil.copyfileobj(plain, packed)
    Path(source).unlink()


@final
class DailyFile(TimedRotatingFileHandler):
    def __init__(self, filename: str | PathLike[str], *, kept: int = 0) -> None:
        super().__init__(filename, when="midnight", backupCount=kept, encoding="utf-8")
        self.namer = compressed_name
        self.rotator = compress
