import logging
import logging.config
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"
LARGEST_LOG: Final = 5_000_000
KEPT_LOGS: Final = 3


def default_logging(log_file: Path) -> dict[str, object]:
    return {
        "formatters": {"plain": {"format": LOG_FORMAT}},
        "handlers": {
            "stderr": {"class": "logging.StreamHandler", "formatter": "plain", "stream": "ext://sys.stderr"},
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "plain",
                "filename": str(log_file),
                "maxBytes": LARGEST_LOG,
                "backupCount": KEPT_LOGS,
                "encoding": "utf-8",
            },
        },
        "root": {"level": "INFO", "handlers": ["stderr", "file"]},
    }


def apply_logging(config: Mapping[str, object]) -> None:
    try:
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False, **config})
    except ValueError as error:
        message = f"invalid [logging] section: {error}"
        raise SystemExit(message) from error
    logging.captureWarnings(capture=True)
