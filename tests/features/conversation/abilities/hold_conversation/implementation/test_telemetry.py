from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import no_stall


def test_no_stall_takes_a_wait_and_does_nothing() -> None:
    assert no_stall(0.5) is None
