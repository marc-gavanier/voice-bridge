import json
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    Activity,
    activity_of,
    listen_to_claude,
    tell_bridge,
)


def hook(name: str, **fields: object) -> str:
    return json.dumps({"session_id": "abc123", "hook_event_name": name, **fields})


def test_a_prompt_submitted_makes_claude_busy() -> None:
    assert activity_of(hook("UserPromptSubmit", prompt="Bonjour")) == "busy"


def test_a_stop_with_nothing_in_the_background_makes_claude_idle() -> None:
    assert activity_of(hook("Stop", background_tasks=[], session_crons=[])) == "idle"


def test_a_stop_with_background_tasks_keeps_claude_busy() -> None:
    task = {"id": "task-001", "type": "subagent", "status": "running", "description": "search"}
    assert activity_of(hook("Stop", background_tasks=[task])) == "busy"


def test_a_stop_with_only_scheduled_wakeups_makes_claude_idle() -> None:
    cron = {"id": "cron-001", "schedule": "0 9 * * 1-5", "recurring": True, "prompt": "check"}
    assert activity_of(hook("Stop", background_tasks=[], session_crons=[cron])) == "idle"


def test_a_stop_without_the_task_registry_makes_claude_idle() -> None:
    assert activity_of(hook("Stop")) == "idle"


def test_an_api_error_makes_claude_idle() -> None:
    assert activity_of(hook("StopFailure", error="rate_limit")) == "idle"


def test_the_end_of_the_session_makes_claude_idle() -> None:
    assert activity_of(hook("SessionEnd", reason="other")) == "idle"


def test_another_hook_says_nothing() -> None:
    assert activity_of(hook("PreToolUse", tool_name="Bash")) is None


def test_an_unreadable_hook_input_says_nothing() -> None:
    assert activity_of("not json") is None


def test_telling_a_bridge_that_is_not_running_does_nothing(tmp_path: Path) -> None:
    assert tell_bridge(tmp_path / "activity.sock", "idle") is None


@asynccontextmanager
async def listening(path: Path) -> AsyncGenerator[MemoryObjectReceiveStream[Activity]]:
    heard_in, heard_out = anyio.create_memory_object_stream[Activity](10)
    async with heard_in, heard_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(listen_to_claude, path, heard_in.send)
        await anyio.wait_all_tasks_blocked()
        yield heard_out
        tasks.cancel_scope.cancel()


def send_raw(path: Path, data: bytes) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(path))
        connection.sendall(data)


@pytest.mark.anyio
async def test_the_bridge_hears_what_the_hook_tells(tmp_path: Path) -> None:
    path = tmp_path / "voice-bridge" / "activity.sock"
    async with listening(path) as heard:
        await anyio.to_thread.run_sync(tell_bridge, path, "busy")
        activity = await heard.receive()
    assert activity == "busy"


@pytest.mark.anyio
async def test_the_bridge_ignores_an_unknown_word(tmp_path: Path) -> None:
    path = tmp_path / "activity.sock"
    async with listening(path) as heard:
        await anyio.to_thread.run_sync(send_raw, path, b"sleeping\n")
        await anyio.to_thread.run_sync(tell_bridge, path, "idle")
        activity = await heard.receive()
    assert activity == "idle"


@pytest.mark.anyio
async def test_the_bridge_ignores_a_connection_closed_without_a_word(tmp_path: Path) -> None:
    path = tmp_path / "activity.sock"
    async with listening(path) as heard:
        await anyio.to_thread.run_sync(send_raw, path, b"")
        await anyio.to_thread.run_sync(tell_bridge, path, "idle")
        activity = await heard.receive()
    assert activity == "idle"


@pytest.mark.anyio
async def test_a_socket_left_by_a_former_run_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "activity.sock"
    _ = path.write_text("stale", encoding="utf-8")
    async with listening(path) as heard:
        await anyio.to_thread.run_sync(tell_bridge, path, "busy")
        activity = await heard.receive()
    assert activity == "busy"
