import logging
import logging.config
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

from voice_bridge.configuration.log_config import apply_logging, default_logging

LARGEST_LOG = 5_000_000


@pytest.fixture(autouse=True)
def plain_logging() -> Iterator[None]:
    yield
    logging.captureWarnings(capture=False)
    logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})


def logged_to(log_file: Path, config: dict[str, object]) -> str:
    apply_logging(config)
    logging.getLogger("voice_bridge.test").info("a line to find")
    return log_file.read_text(encoding="utf-8")


def file_section(log_file: Path) -> dict[str, object]:
    return {
        "handlers": {"file": {"class": "logging.FileHandler", "filename": str(log_file)}},
        "root": {"level": "INFO", "handlers": ["file"]},
    }


def test_the_default_log_writes_to_the_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "voice-bridge.log"
    assert "INFO voice_bridge.test a line to find" in logged_to(log_file, default_logging(log_file))


def test_the_default_log_rotates_at_five_megabytes(tmp_path: Path) -> None:
    assert default_logging(tmp_path / "voice-bridge.log")["handlers"] == {
        "stderr": {"class": "logging.StreamHandler", "formatter": "plain", "stream": "ext://sys.stderr"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "plain",
            "filename": str(tmp_path / "voice-bridge.log"),
            "maxBytes": LARGEST_LOG,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    }


def test_a_section_without_a_version_applies(tmp_path: Path) -> None:
    log_file = tmp_path / "chosen.log"
    assert "a line to find" in logged_to(log_file, file_section(log_file))


def test_a_section_keeps_the_loggers_created_before_it(tmp_path: Path) -> None:
    log_file = tmp_path / "chosen.log"
    _ = logging.getLogger("voice_bridge.early")
    apply_logging(file_section(log_file))
    logging.getLogger("voice_bridge.early").info("an early line")
    assert "an early line" in log_file.read_text(encoding="utf-8")


def test_warnings_reach_the_log(tmp_path: Path) -> None:
    log_file = tmp_path / "chosen.log"
    apply_logging(file_section(log_file))
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.warn("a warning to find", UserWarning, stacklevel=1)
    assert "a warning to find" in log_file.read_text(encoding="utf-8")


def test_an_invalid_section_stops_with_a_message_naming_it() -> None:
    with pytest.raises(SystemExit, match=r"^invalid \[logging\] section: "):
        apply_logging({"handlers": {"broken": {"class": "logging.NoSuchHandler"}}})
