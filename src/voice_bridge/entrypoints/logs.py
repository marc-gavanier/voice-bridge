import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"
LARGEST_LOG: Final = 5_000_000
KEPT_LOGS: Final = 3


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stderr),
        RotatingFileHandler(log_file, maxBytes=LARGEST_LOG, backupCount=KEPT_LOGS, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers, force=True)
    logging.captureWarnings(capture=True)
