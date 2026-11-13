import json
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    AgentFinished,
    AgentStarted,
    Busy,
    Idle,
    News,
    Task,
    listen_to_claude,
    news_of,
    tell_bridge,
)

SEARCH = {"id": "a1", "type": "subagent", "status": "running", "description": "Search the notes", "agent_type": "x"}


def hook(name: str, **fields: object) -> str:
    return json.dumps({"session_id": "abc123", "hook_event_name": name, **fields})


def test_a_prompt_submitted_makes_claude_busy() -> None:
    assert news_of(hook("UserPromptSubmit", prompt="Bonjour")) == Busy()


def test_a_stop_with_nothing_in_the_background_makes_claude_idle() -> None:
    assert news_of(hook("Stop", background_tasks=[], session_crons=[])) == Idle()


def test_a_stop_with_background_tasks_keeps_claude_busy_and_tells_the_tasks() -> None:
    assert news_of(hook("Stop", background_tasks=[SEARCH])) == Busy(
        tasks=(Task(id="a1", description="Search the notes"),)
    )


def test_a_stop_with_only_scheduled_wakeups_makes_claude_idle() -> None:
    cron = {"id": "cron-001", "schedule": "0 9 * * 1-5", "recurring": True, "prompt": "check"}
    assert news_of(hook("Stop", background_tasks=[], session_crons=[cron])) == Idle()


def test_a_stop_without_the_task_registry_makes_claude_idle() -> None:
    assert news_of(hook("Stop")) == Idle()


def test_an_api_error_makes_claude_idle() -> None:
    assert news_of(hook("StopFailure", error="rate_limit")) == Idle()


def test_the_end_of_the_session_makes_claude_idle() -> None:
    assert news_of(hook("SessionEnd", reason="other")) == Idle()


def test_a_subagent_starting_tells_its_id_and_type() -> None:
    assert news_of(hook("SubagentStart", agent_id="a1", agent_type="general-purpose")) == AgentStarted(
        agent_id="a1", agent_type="general-purpose"
    )


def test_a_subagent_stopping_tells_its_last_message_and_the_tasks() -> None:
    stopped = hook(
        "SubagentStop",
        agent_id="a1",
        agent_type="general-purpose",
        last_assistant_message="Found it.",
        background_tasks=[SEARCH],
    )
    assert news_of(stopped) == AgentFinished(
        agent_id="a1",
        agent_type="general-purpose",
        last_message="Found it.",
        tasks=(Task(id="a1", description="Search the notes"),),
    )


def test_a_subagent_stopping_without_a_message_tells_an_empty_one() -> None:
    assert news_of(hook("SubagentStop", agent_id="a1", agent_type="", last_assistant_message=None)) == AgentFinished(
        agent_id="a1"
    )


def test_another_hook_says_nothing() -> None:
    assert news_of(hook("PreToolUse", tool_name="Bash")) is None


def test_an_unreadable_hook_input_says_nothing() -> None:
    assert news_of("not json") is None


def test_telling_a_bridge_that_is_not_running_does_nothing(tmp_path: Path) -> None:
    assert tell_bridge(tmp_path / "activity.sock", Idle()) is None


@asynccontextmanager
async def listening(path: Path) -> AsyncGenerator[MemoryObjectReceiveStream[News]]:
    heard_in, heard_out = anyio.create_memory_object_stream[News](10)
    async with heard_in, heard_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(listen_to_claude, path, heard_in.send)
        await anyio.wait_all_tasks_blocked()
        yield heard_out
        tasks.cancel_scope.cancel()


def send_raw(path: Path, data: bytes) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(path))
        connection.sendall(data)


async def heard_after(path: Path, *raw: bytes, news: News) -> News:
    async with listening(path) as heard:
        for data in raw:
            await anyio.to_thread.run_sync(send_raw, path, data)
        await anyio.to_thread.run_sync(tell_bridge, path, news)
        return await heard.receive()


@pytest.mark.anyio
async def test_the_bridge_hears_what_the_hook_tells(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "voice-bridge" / "activity.sock", news=Busy()) == Busy()


@pytest.mark.anyio
async def test_the_bridge_hears_a_finished_agent_with_its_whole_last_message(tmp_path: Path) -> None:
    finished = AgentFinished(agent_id="a1", agent_type="general-purpose", last_message="Found it.\n" * 1000)
    assert await heard_after(tmp_path / "activity.sock", news=finished) == finished


@pytest.mark.anyio
async def test_the_bridge_ignores_an_unknown_message(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b'{"kind": "sleeping"}\n', news=Idle()) == Idle()


@pytest.mark.anyio
async def test_the_bridge_ignores_a_bare_word(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b"busy\n", news=Idle()) == Idle()


@pytest.mark.anyio
async def test_the_bridge_ignores_a_connection_closed_without_a_message(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b"", news=Idle()) == Idle()


@pytest.mark.anyio
async def test_a_socket_left_by_a_former_run_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "activity.sock"
    _ = path.write_text("stale", encoding="utf-8")
    assert await heard_after(path, news=Busy()) == Busy()


@pytest.mark.anyio
async def test_the_bridge_logs_an_agent_started(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await heard_after(tmp_path / "activity.sock", news=AgentStarted(agent_id="a1", agent_type="Explore"))
    assert "agent a1 started, of type 'Explore'" in caplog.text


@pytest.mark.anyio
async def test_the_bridge_logs_an_agent_finished(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await heard_after(tmp_path / "activity.sock", news=AgentFinished(agent_id="a1", agent_type="Explore"))
    assert "agent a1 finished, of type 'Explore'" in caplog.text


@pytest.mark.anyio
async def test_the_bridge_logs_that_claude_is_busy(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await heard_after(tmp_path / "activity.sock", news=Busy())
    assert "Claude Code is busy" in caplog.text
