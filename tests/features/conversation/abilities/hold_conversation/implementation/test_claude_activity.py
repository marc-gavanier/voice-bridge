import json
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import (
    Activity,
    ToolCall,
    ToolCallCompleted,
    ToolCallUpdate,
    TurnEnded,
    TurnStarted,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    AgentActed,
    AgentFinished,
    AgentStarted,
    Busy,
    Idle,
    News,
    Task,
    activity_of,
    listen_to_claude,
    news_of,
    tell_bridge,
)
from voice_bridge.features.conversation.domain import board

SEARCH = {"id": "a1", "type": "subagent", "status": "running", "description": "Search the notes", "agent_type": "x"}
SEARCH_TASK = Task(id="a1", type="subagent", description="Search the notes", agent_type="x")


MORNING = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)


def hook(name: str, **fields: object) -> str:
    return json.dumps({"session_id": "abc123", "hook_event_name": name, **fields})


def news_at(event: str) -> News | None:
    return news_of(event, at=MORNING)


def action_of(tool: str, **tool_input: object) -> str:
    acted = news_at(hook("PreToolUse", tool_name=tool, tool_input=tool_input, agent_id="a1", agent_type="Explore"))
    return acted.action if isinstance(acted, AgentActed) else ""


def test_a_prompt_submitted_makes_claude_busy() -> None:
    assert news_at(hook("UserPromptSubmit", prompt="Bonjour")) == Busy()


def test_a_stop_with_nothing_in_the_background_makes_claude_idle() -> None:
    assert news_at(hook("Stop", background_tasks=[], session_crons=[])) == Idle(tasks=())


def test_a_stop_with_background_tasks_keeps_claude_busy_and_tells_the_tasks() -> None:
    assert news_at(hook("Stop", background_tasks=[SEARCH])) == Busy(tasks=(SEARCH_TASK,))


def test_a_stop_with_only_scheduled_wakeups_makes_claude_idle() -> None:
    cron = {"id": "cron-001", "schedule": "0 9 * * 1-5", "recurring": True, "prompt": "check"}
    assert news_at(hook("Stop", background_tasks=[], session_crons=[cron])) == Idle(tasks=())


def test_a_stop_without_the_task_registry_makes_claude_idle_with_no_task_list() -> None:
    assert news_at(hook("Stop")) == Idle(tasks=None)


def test_an_api_error_makes_claude_idle() -> None:
    assert news_at(hook("StopFailure", error="rate_limit")) == Idle()


def test_the_end_of_the_session_makes_claude_idle() -> None:
    assert news_at(hook("SessionEnd", reason="other")) == Idle()


def test_a_subagent_starting_tells_its_id_and_type() -> None:
    assert news_at(hook("SubagentStart", agent_id="a1", agent_type="general-purpose")) == AgentStarted(
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
    assert news_at(stopped) == AgentFinished(
        agent_id="a1",
        agent_type="general-purpose",
        last_message="Found it.",
        tasks=(SEARCH_TASK,),
    )


def test_a_subagent_stopping_without_a_message_tells_an_empty_one() -> None:
    assert news_at(hook("SubagentStop", agent_id="a1", agent_type="", last_assistant_message=None)) == AgentFinished(
        agent_id="a1"
    )


def test_a_subagent_stopping_without_the_task_registry_tells_no_task_list() -> None:
    assert news_at(hook("SubagentStop", agent_id="a1", agent_type="Explore")) == AgentFinished(
        agent_id="a1", agent_type="Explore", tasks=None
    )


def test_another_hook_says_nothing() -> None:
    assert news_at(hook("PostToolUse", tool_name="Bash", agent_id="a1")) is None


def test_a_tool_call_of_the_main_agent_says_nothing() -> None:
    assert news_at(hook("PreToolUse", tool_name="Bash", tool_input={"command": "ls"})) is None


def test_a_tool_call_of_an_agent_tells_its_action_and_when() -> None:
    called = hook(
        "PreToolUse",
        tool_name="Bash",
        tool_input={"command": "gh pr checks", "description": "Watch the CI"},
        agent_id="a1",
    )
    assert news_at(called) == AgentActed(agent_id="a1", action="Watch the CI", at=MORNING)


def test_a_command_is_told_by_its_description_only() -> None:
    assert action_of("Bash", command="gh pr checks --watch", description="Watch the CI") == "Watch the CI"


def test_a_command_without_a_description_is_told_by_the_tool_alone() -> None:
    assert action_of("Bash", command="cat ~/.ssh/id_ed25519") == "Bash"


def test_a_file_read_is_told_by_the_file_name_only() -> None:
    assert action_of("Read", file_path="/home/marc/project/src/board.py") == "Read board.py"


def test_a_file_edited_is_told_by_the_file_name_only() -> None:
    assert action_of("Edit", file_path="/home/marc/board.py", old_string="a", new_string="b") == "Edit board.py"


def test_a_file_written_is_told_by_the_file_name_only() -> None:
    assert action_of("Write", file_path="/home/marc/notes.md", content="secret") == "Write notes.md"


def test_an_agent_started_is_told_by_its_task() -> None:
    assert action_of("Agent", description="Find API endpoints", prompt="Long prompt") == "Agent Find API endpoints"


def test_a_web_search_is_told_by_its_query() -> None:
    assert action_of("WebSearch", query="claude code hooks") == "WebSearch claude code hooks"


def test_a_page_fetched_is_told_by_its_host_only() -> None:
    assert action_of("WebFetch", url="https://code.claude.com/docs/en/hooks.md?token=x", prompt="Read") == (
        "WebFetch code.claude.com"
    )


def test_a_search_in_files_is_told_by_its_pattern() -> None:
    assert action_of("Grep", pattern="agent_id", path="/home/marc") == "Grep agent_id"


def test_a_search_of_file_names_is_told_by_its_pattern() -> None:
    assert action_of("Glob", pattern="**/*.py") == "Glob **/*.py"


def test_another_tool_is_told_by_its_name_alone() -> None:
    assert action_of("mcp__voice__reply", text="Bonjour") == "mcp__voice__reply"


def test_a_detail_that_is_not_text_is_left_out() -> None:
    assert action_of("Read", file_path=42) == "Read"


def test_an_action_is_told_on_one_line() -> None:
    assert action_of("Bash", description="Run the tests\nthen  push") == "Run the tests then push"


def test_a_long_action_is_cut() -> None:
    assert action_of("WebSearch", query="a" * 300) == f"WebSearch {'a' * 110}"


def test_an_unreadable_hook_input_says_nothing() -> None:
    assert news_at("not json") is None


def test_telling_a_bridge_that_is_not_running_logs_why(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    tell_bridge(tmp_path / "activity.sock", AgentStarted(agent_id="a1", agent_type="Explore"))
    assert "the activity hook could not tell the bridge that agent a1 started, of type 'Explore'" in caplog.text


SHELL_TASK = Task(id="b1", type="shell", description="tail logs", agent_type="x")
AGENT = board.Task(id="a1", description="Search the notes", kind="x")


def test_a_prompt_submitted_starts_a_turn() -> None:
    assert activity_of(Busy()) == TurnStarted()


def test_a_stop_with_background_tasks_ends_the_turn_with_work_left_and_its_agents() -> None:
    assert activity_of(Busy(tasks=(SEARCH_TASK,))) == TurnEnded(working=True, agents=(AGENT,))


def test_a_task_that_is_not_an_agent_keeps_working_without_being_an_agent() -> None:
    assert activity_of(Busy(tasks=(SHELL_TASK,))) == TurnEnded(working=True, agents=())


def test_a_stop_with_nothing_in_the_background_ends_the_turn_with_no_agent() -> None:
    assert activity_of(Idle(tasks=())) == TurnEnded(agents=())


def test_a_stop_without_the_task_list_ends_the_turn_without_telling_the_agents() -> None:
    assert activity_of(Idle()) == TurnEnded()


def test_an_agent_started_is_a_tool_call_titled_with_its_type() -> None:
    assert activity_of(AgentStarted(agent_id="a1", agent_type="Explore")) == ToolCall(
        tool_call_id="a1", title="Explore"
    )


def test_an_agents_action_updates_its_tool_call_with_the_moment() -> None:
    acted = AgentActed(agent_id="a1", action="Read board.py", at=MORNING)
    assert activity_of(acted) == ToolCallUpdate(tool_call_id="a1", title="Read board.py", at=MORNING)


def test_an_agent_finished_completes_its_tool_call_with_its_last_message_and_the_agents_left() -> None:
    finished = AgentFinished(agent_id="a1", last_message="Found it.", tasks=(SEARCH_TASK,))
    assert activity_of(finished) == ToolCallCompleted(tool_call_id="a1", content="Found it.", agents=(AGENT,))


def test_an_agent_finished_without_the_task_list_tells_no_agents() -> None:
    assert activity_of(AgentFinished(agent_id="a1")) == ToolCallCompleted(tool_call_id="a1")


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


async def heard_after(path: Path, *raw: bytes, news: News) -> Activity:
    async with listening(path) as heard:
        for data in raw:
            await anyio.to_thread.run_sync(send_raw, path, data)
        await anyio.to_thread.run_sync(tell_bridge, path, news)
        return await heard.receive()


@pytest.mark.anyio
async def test_the_bridge_hears_what_the_hook_tells(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "voice-bridge" / "activity.sock", news=Busy()) == TurnStarted()


@pytest.mark.anyio
async def test_the_bridge_hears_a_finished_agent_with_its_whole_last_message(tmp_path: Path) -> None:
    finished = AgentFinished(agent_id="a1", agent_type="general-purpose", last_message="Found it.\n" * 1000)
    assert await heard_after(tmp_path / "activity.sock", news=finished) == ToolCallCompleted(
        tool_call_id="a1", content="Found it.\n" * 1000
    )


@pytest.mark.anyio
async def test_the_bridge_ignores_an_unknown_message(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b'{"kind": "sleeping"}\n', news=Idle()) == TurnEnded()


@pytest.mark.anyio
async def test_the_bridge_ignores_a_bare_word(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b"busy\n", news=Idle()) == TurnEnded()


@pytest.mark.anyio
async def test_the_bridge_ignores_a_connection_closed_without_a_message(tmp_path: Path) -> None:
    assert await heard_after(tmp_path / "activity.sock", b"", news=Idle()) == TurnEnded()


@pytest.mark.anyio
async def test_a_socket_left_by_a_former_run_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "activity.sock"
    _ = path.write_text("stale", encoding="utf-8")
    assert await heard_after(path, news=Busy()) == TurnStarted()


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
async def test_the_bridge_hears_an_agents_action_with_its_moment(tmp_path: Path) -> None:
    acted = AgentActed(agent_id="a1", action="Watch the CI", at=MORNING)
    assert await heard_after(tmp_path / "activity.sock", news=acted) == ToolCallUpdate(
        tool_call_id="a1", title="Watch the CI", at=MORNING
    )


@pytest.mark.anyio
async def test_the_bridge_logs_an_agents_action(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await heard_after(
        tmp_path / "activity.sock", news=AgentActed(agent_id="a1", action="Read board.py", at=MORNING)
    )
    assert "agent a1 did 'Read board.py'" in caplog.text


@pytest.mark.anyio
async def test_the_bridge_logs_that_claude_is_busy(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await heard_after(tmp_path / "activity.sock", news=Busy())
    assert "Claude Code is busy" in caplog.text
