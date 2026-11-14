import logging
from typing import TYPE_CHECKING

import anyio

from voice_bridge.configuration.log_config import LOG_FORMAT, apply_logging, default_logging, kept_days

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping
    from pathlib import Path

    from voice_bridge.configuration.settings import Retention

logger = logging.getLogger(__name__)


def configure_logging(log_file: Path, retention: Retention, section: Mapping[str, object] | None = None) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    apply_logging(default_logging(log_file, kept_days(retention)) if section is None else section)


def log_hook_to(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_file, format=LOG_FORMAT, level=logging.INFO, encoding="utf-8")


def run_logged[*Arguments](
    function: Callable[[*Arguments], Coroutine[object, object, None]], *arguments: *Arguments
) -> None:
    try:
        anyio.run(function, *arguments)
    except Exception:
        logger.exception("stopped on an unexpected error")
        raise
