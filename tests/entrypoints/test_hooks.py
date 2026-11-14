import json
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from voice_bridge.configuration.language import language_pack
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    Busy,
    News,
    listen_to_claude,
)

SCRIPTS = Path(sys.executable).parent
PROMPT = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "Bonjour"}).encode()
AGENT_TOOL = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "agent_id": "a1"}).encode()


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
async def listening(socket: Path) -> AsyncGenerator[MemoryObjectReceiveStream[News]]:
    heard_in, heard_out = anyio.create_memory_object_stream[News](1)
    async with heard_in, heard_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(listen_to_claude, socket, heard_in.send)
        await anyio.wait_all_tasks_blocked()
        yield heard_out
        tasks.cancel_scope.cancel()


async def heard_from_the_hook(home: Path, socket: Path) -> News:
    async with listening(socket) as heard:
        arguments = ["--socket", str(socket), "--log-file", str(home / "bridge.log")]
        _ = await run_hook("voice-bridge-activity-hook", arguments, PROMPT, configured_with_an_unknown_key(home))
        return await heard.receive()


@pytest.mark.anyio
async def test_the_activity_hook_ignores_a_config_file_it_cannot_read(tmp_path: Path) -> None:
    assert await heard_from_the_hook(tmp_path, tmp_path / "a.sock") == Busy()


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
