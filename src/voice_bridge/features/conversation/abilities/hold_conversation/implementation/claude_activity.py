import logging
import socket
from datetime import datetime
from pathlib import PurePath
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Literal, assert_never
from urllib.parse import urlsplit

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import (
    Activity,
    ToolCall,
    ToolCallCompleted,
    ToolCallUpdate,
    TurnEnded,
    TurnStarted,
)
from voice_bridge.features.conversation.domain import board

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from anyio.abc import SocketStream

logger = logging.getLogger(__name__)

LONGEST_LINE: Final = 1024 * 1024
SEND_TIMEOUT: Final = 1.0
LONGEST_ACTION: Final = 120
AGENT_TASK: Final = "subagent"


class _Message(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class Task(_Message):
    id: str = ""
    type: str = ""
    description: str = ""
    agent_type: str = ""


class Busy(_Message):
    kind: Literal["busy"] = "busy"
    tasks: tuple[Task, ...] | None = None


class Idle(_Message):
    kind: Literal["idle"] = "idle"
    tasks: tuple[Task, ...] | None = None


class AgentStarted(_Message):
    kind: Literal["started"] = "started"
    agent_id: str
    agent_type: str = ""


class AgentFinished(_Message):
    kind: Literal["finished"] = "finished"
    agent_id: str
    agent_type: str = ""
    last_message: str = ""
    tasks: tuple[Task, ...] | None = None


class AgentActed(_Message):
    kind: Literal["acted"] = "acted"
    agent_id: str
    action: str
    at: datetime


type News = Annotated[Busy | Idle | AgentStarted | AgentFinished | AgentActed, Field(discriminator="kind")]

NEWS: Final = TypeAdapter[News](News)


class _HookEvent(BaseModel):
    hook_event_name: str = ""
    background_tasks: tuple[Task, ...] | None = None
    agent_id: str = ""
    agent_type: str = ""
    last_assistant_message: str | None = None
    tool_name: str = ""
    tool_input: dict[str, JsonValue] = Field(default_factory=dict)


def _detail(tool: str, fields: dict[str, str]) -> str:
    match tool:
        case "Read" | "Edit" | "Write":
            return PurePath(fields.get("file_path", "")).name
        case "WebFetch":
            return urlsplit(fields.get("url", "")).hostname or ""
        case "Agent" | "Task":
            return fields.get("description", "")
        case "WebSearch":
            return fields.get("query", "")
        case "Grep" | "Glob":
            return fields.get("pattern", "")
        case _:
            return ""


def _action(hook: _HookEvent) -> str:
    fields = {key: value for key, value in hook.tool_input.items() if isinstance(value, str)}
    detail = _detail(hook.tool_name, fields)
    described = fields.get("description", "") if hook.tool_name == "Bash" else ""
    said = described or (f"{hook.tool_name} {detail}" if detail else hook.tool_name)
    return " ".join(said.split())[:LONGEST_ACTION]


def _agent_news(hook: _HookEvent, at: datetime) -> AgentStarted | AgentFinished | AgentActed | None:
    match hook.hook_event_name:
        case "SubagentStart":
            return AgentStarted(agent_id=hook.agent_id, agent_type=hook.agent_type)
        case "PreToolUse":
            return AgentActed(agent_id=hook.agent_id, action=_action(hook), at=at) if hook.agent_id else None
        case _:
            return AgentFinished(
                agent_id=hook.agent_id,
                agent_type=hook.agent_type,
                last_message=hook.last_assistant_message or "",
                tasks=hook.background_tasks,
            )


def news_of(event: str, *, at: datetime) -> News | None:
    try:
        hook = _HookEvent.model_validate_json(event)
    except ValidationError:
        return None
    match hook.hook_event_name:
        case "UserPromptSubmit":
            return Busy()
        case "Stop":
            return Busy(tasks=hook.background_tasks) if hook.background_tasks else Idle(tasks=hook.background_tasks)
        case "StopFailure" | "SessionEnd":
            return Idle()
        case "SubagentStart" | "SubagentStop" | "PreToolUse":
            return _agent_news(hook, at)
        case _:
            return None


def _said(news: News) -> str:
    match news:
        case Busy() | Idle():
            return f"Claude Code is {news.kind}"
        case AgentStarted():
            return f"agent {news.agent_id} started, of type {news.agent_type!r}"
        case AgentFinished():
            return f"agent {news.agent_id} finished, of type {news.agent_type!r}"
        case AgentActed():
            return f"agent {news.agent_id} did {news.action!r}"
        case _:
            assert_never(news)


def _agents(tasks: tuple[Task, ...] | None) -> tuple[board.Task, ...] | None:
    if tasks is None:
        return None
    return tuple(
        board.Task(id=task.id, description=task.description, kind=task.agent_type)
        for task in tasks
        if task.type == AGENT_TASK
    )


def activity_of(news: News) -> Activity:
    match news:
        case Busy(tasks=None):
            return TurnStarted()
        case Busy(tasks=tasks):
            return TurnEnded(working=True, agents=_agents(tasks))
        case Idle(tasks=tasks):
            return TurnEnded(agents=_agents(tasks))
        case AgentStarted(agent_id=agent_id, agent_type=agent_type):
            return ToolCall(tool_call_id=agent_id, title=agent_type)
        case AgentActed(agent_id=agent_id, action=action, at=at):
            return ToolCallUpdate(tool_call_id=agent_id, title=action, at=at)
        case AgentFinished(agent_id=agent_id, last_message=last_message, tasks=tasks):
            return ToolCallCompleted(tool_call_id=agent_id, content=last_message, agents=_agents(tasks))
        case _:
            assert_never(news)


def tell_bridge(path: Path, news: News) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SEND_TIMEOUT)
        try:
            connection.connect(str(path))
            connection.sendall(news.model_dump_json().encode() + b"\n")
        except OSError as error:
            logger.warning("the activity hook could not tell the bridge that %s: %s", _said(news), error)


async def _read_news(stream: SocketStream) -> News | None:
    async with stream:
        try:
            line = await BufferedByteReceiveStream(stream).receive_until(b"\n", LONGEST_LINE)
        except anyio.EndOfStream, anyio.IncompleteRead, anyio.DelimiterNotFound:
            return None
    try:
        return NEWS.validate_json(line)
    except ValidationError:
        return None


async def listen_to_claude(path: Path, heard: Callable[[Activity], Awaitable[None]]) -> None:
    await anyio.Path(path).parent.mkdir(parents=True, exist_ok=True)
    await anyio.Path(path).unlink(missing_ok=True)

    async def handle(stream: SocketStream) -> None:
        news = await _read_news(stream)
        if news is None:
            return
        logger.info("%s", _said(news))
        await heard(activity_of(news))

    async with await anyio.create_unix_listener(path) as listener:
        await listener.serve(handle)
