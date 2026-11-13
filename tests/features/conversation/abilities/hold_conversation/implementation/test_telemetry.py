from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import (
    no_stall,
    no_telemetry,
)
from voice_bridge.features.conversation.domain.turn_trace import Counted


def test_no_telemetry_takes_a_report_and_does_nothing() -> None:
    assert no_telemetry(Counted(name="interruption")) is None


def test_no_stall_takes_a_wait_and_does_nothing() -> None:
    assert no_stall(0.5) is None
