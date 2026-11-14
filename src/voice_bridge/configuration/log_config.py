import logging
import logging.config
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from voice_bridge.configuration.settings import Retention

LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"


def kept_days(retention: Retention) -> int:
    return 0 if retention == "forever" else retention


def default_logging(log_file: Path, kept: int) -> dict[str, object]:
    return {
        "formatters": {"plain": {"format": LOG_FORMAT}},
        "handlers": {
            "stderr": {"class": "logging.StreamHandler", "formatter": "plain", "stream": "ext://sys.stderr"},
            "file": {
                "class": "voice_bridge.libraries.rotation.daily.DailyFile",
                "formatter": "plain",
                "filename": str(log_file),
                "kept": kept,
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
