import json
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from voice_bridge.configuration.language import language_pack
from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import (
    Activity,
    ToolCallUpdate,
    TurnStarted,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    listen_to_claude,
)

SCRIPTS = Path(sys.executable).parent
PROMPT = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "Bonjour"}).encode()
AGENT_TOOL = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "agent_id": "a1"}).encode()
AGENT_COMMAND = json.dumps(
    {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr checks --watch", "description": "Watch the CI"},
        "agent_id": "a1",
        "agent_type": "general-purpose",
    }
).encode()


def configured_with_an_unknown_key(home: Path) -> dict[str, str]:
    config = home / "voice-bridge" / "config.toml"
    config.parent.mkdir(parents=True)
    _ = config.write_text(
        'language = "fr"\nnot_a_setting = 1\n[speech]\nnot_a_speech_setting = 1.2\n', encoding="utf-8"
    )
    return {**os.environ, "XDG_CONFIG_HOME": str(home)}


async def run_hook(name: str, arguments: list[str], event: bytes, environment: dict[str, str]) -> str:
    done = await anyio.run_process([str(SCRIPTS / name), *arguments], input=event, env=environment, check=True)
    return done.stdout.decode()


@asynccontextmanager
async def listening(socket: Path) -> AsyncGenerator[MemoryObjectReceiveStream[Activity]]:
    heard_in, heard_out = anyio.create_memory_object_stream[Activity](1)
    async with heard_in, heard_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(listen_to_claude, socket, heard_in.send)
        await anyio.wait_all_tasks_blocked()
        yield heard_out
        tasks.cancel_scope.cancel()


async def heard_from_the_hook(home: Path, socket: Path, event: bytes = PROMPT) -> Activity:
    async with listening(socket) as heard:
        arguments = ["--socket", str(socket), "--log-file", str(home / "bridge.log")]
        _ = await run_hook("voice-bridge-activity-hook", arguments, event, configured_with_an_unknown_key(home))
        return await heard.receive()


@pytest.mark.anyio
async def test_the_activity_hook_ignores_a_config_file_it_cannot_read(tmp_path: Path) -> None:
    assert await heard_from_the_hook(tmp_path, tmp_path / "a.sock") == TurnStarted()


async def action_told_in_time(home: Path) -> tuple[str, bool]:
    before = datetime.now().astimezone()
    heard = await heard_from_the_hook(home, home / "a.sock", AGENT_COMMAND)
    after = datetime.now().astimezone()
    return (heard.title, before <= heard.at <= after) if isinstance(heard, ToolCallUpdate) else ("", False)


@pytest.mark.anyio
async def test_the_activity_hook_tells_an_agents_tool_call_and_when_it_was_made(tmp_path: Path) -> None:
    assert await action_told_in_time(tmp_path) == ("Watch the CI", True)


@pytest.mark.anyio
async def test_the_tool_hook_ignores_a_config_file_it_cannot_read(tmp_path: Path) -> None:
    stop_flag = tmp_path / "stop"
    _ = stop_flag.write_text("", encoding="utf-8")
    arguments = ["--stop-flag", str(stop_flag), "--language", "fr", "--log-file", str(tmp_path / "bridge.log")]
    answer = await run_hook("voice-bridge-tool-hook", arguments, AGENT_TOOL, configured_with_an_unknown_key(tmp_path))
    assert json.loads(answer)["hookSpecificOutput"]["permissionDecisionReason"] == language_pack("fr").stop_refusal


@pytest.mark.anyio
async def test_the_activity_hook_logs_that_it_cannot_reach_the_bridge(tmp_path: Path) -> None:
    log_file = tmp_path / "log" / "bridge.log"
    arguments = ["--socket", str(tmp_path / "absent.sock"), "--log-file", str(log_file)]
    _ = await run_hook("voice-bridge-activity-hook", arguments, PROMPT, dict(os.environ))
    assert "the activity hook could not tell the bridge that Claude Code is busy" in log_file.read_text(
        encoding="utf-8"
    )
