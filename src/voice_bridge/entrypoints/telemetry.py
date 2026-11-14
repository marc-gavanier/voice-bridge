import logging
import os
from importlib.util import find_spec
from typing import TYPE_CHECKING

from voice_bridge.configuration.settings import APP_NAME
from voice_bridge.configuration.telemetry import exports_telemetry, reports_errors
from voice_bridge.libraries.rotation.daily import DailyFile
from voice_bridge.libraries.rotation.text import RotatingText

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from sentry_sdk.transport import Transport

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Telemetry

logger = logging.getLogger(__name__)


def chosen_telemetry(
    clock: Callable[[], float], directory: Path, kept: int, attributes: Mapping[str, str | float | bool]
) -> tuple[Telemetry, Callable[[float], None]]:
    from voice_bridge.features.conversation.abilities.hold_conversation.implementation.open_telemetry import (
        OpenTelemetry,
        writing_to,
    )

    if exports_telemetry(os.environ):
        adapter = OpenTelemetry.from_globals(clock)
        logger.info("telemetry exported over OTLP")
        return adapter, adapter.stalled
    directory.mkdir(parents=True, exist_ok=True)
    providers = writing_to(
        RotatingText(DailyFile(directory / "traces.jsonl", kept=kept)),
        RotatingText(DailyFile(directory / "metrics.jsonl", kept=kept)),
        {"service.name": APP_NAME, **attributes},
    )
    adapter = OpenTelemetry.from_providers(*providers, clock)
    logger.info("telemetry written to %s", directory)
    return adapter, adapter.stalled


def report_errors(transport: Transport | None = None) -> bool:
    if not reports_errors(os.environ) or find_spec("sentry_sdk") is None:
        return False
    import sentry_sdk

    _ = sentry_sdk.init(max_breadcrumbs=0, include_local_variables=False, transport=transport)
    logger.info("errors reported to Sentry")
    return True
