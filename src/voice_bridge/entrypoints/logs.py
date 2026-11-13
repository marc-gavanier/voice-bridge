from typing import TYPE_CHECKING

from voice_bridge.configuration.log_config import apply_logging, default_logging

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def configure_logging(log_file: Path, section: Mapping[str, object] | None = None) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    apply_logging(default_logging(log_file) if section is None else section)
