import logging
import os
from importlib.util import find_spec
from typing import TYPE_CHECKING

from voice_bridge.configuration.telemetry import exports_telemetry
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import (
    no_stall,
    no_telemetry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Telemetry

logger = logging.getLogger(__name__)


def chosen_telemetry(clock: Callable[[], float]) -> tuple[Telemetry, Callable[[float], None]]:
    if not exports_telemetry(os.environ) or find_spec("opentelemetry") is None:
        return no_telemetry, no_stall
    from voice_bridge.features.conversation.abilities.hold_conversation.implementation.open_telemetry import (
        OpenTelemetry,
    )

    adapter = OpenTelemetry.from_globals(clock)
    logger.info("telemetry exported over OTLP")
    return adapter, adapter.stalled
