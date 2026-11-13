import logging
from typing import TYPE_CHECKING

import anyio

from voice_bridge.configuration.log_config import apply_logging, default_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping
    from pathlib import Path

logger = logging.getLogger(__name__)


def configure_logging(log_file: Path, section: Mapping[str, object] | None = None) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    apply_logging(default_logging(log_file) if section is None else section)


def run_logged[*Arguments](
    function: Callable[[*Arguments], Coroutine[object, object, None]], *arguments: *Arguments
) -> None:
    try:
        anyio.run(function, *arguments)
    except Exception:
        logger.exception("stopped on an unexpected error")
        raise
