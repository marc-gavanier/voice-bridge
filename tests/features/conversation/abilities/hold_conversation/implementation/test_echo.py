import anyio
import pytest

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import (
    AgentMessageChunk,
    Prompt,
    SessionUpdate,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.echo import Echo

pytestmark = pytest.mark.anyio


async def echoed(prompt: Prompt) -> SessionUpdate:
    updates_in, updates_out = anyio.create_memory_object_stream[SessionUpdate](1)
    async with updates_in, updates_out:
        await Echo(updates=updates_in).prompt(prompt)
        return await updates_out.receive()


async def test_the_echo_answers_a_prompt_with_its_own_words() -> None:
    assert await echoed(Prompt(text="Bonjour.", acknowledgement="Voyons.")) == AgentMessageChunk(text="Bonjour.")


async def test_the_echo_logs_what_it_repeats(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await echoed(Prompt(text="Attends.", interrupted=True, acknowledgement="D'accord."))
    assert "repeating 'Attends.' after an interruption, acknowledged with \"D'accord.\"" in caplog.text


async def test_closing_the_echo_ends_nothing(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    updates_in, updates_out = anyio.create_memory_object_stream[SessionUpdate](1)
    async with updates_in, updates_out:
        await Echo(updates=updates_in).close()
    assert "the rehearsal has no assistant to end" in caplog.text
