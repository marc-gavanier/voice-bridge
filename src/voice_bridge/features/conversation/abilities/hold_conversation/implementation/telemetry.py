from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice_bridge.features.conversation.domain.turn_trace import Report


def no_telemetry(_report: Report, /) -> None:
    return None


def no_stall(_seconds: float, /) -> None:
    return None
