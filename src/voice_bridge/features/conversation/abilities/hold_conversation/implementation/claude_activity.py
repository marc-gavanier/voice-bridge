import logging
import socket
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Literal, assert_never

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from anyio.abc import SocketStream

logger = logging.getLogger(__name__)

LONGEST_LINE: Final = 1024 * 1024
SEND_TIMEOUT: Final = 1.0


class _Message(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class Task(_Message):
    id: str = ""
    description: str = ""


class Busy(_Message):
    kind: Literal["busy"] = "busy"
    tasks: tuple[Task, ...] = ()


class Idle(_Message):
    kind: Literal["idle"] = "idle"


class AgentStarted(_Message):
    kind: Literal["started"] = "started"
    agent_id: str
    agent_type: str = ""


class AgentFinished(_Message):
    kind: Literal["finished"] = "finished"
    agent_id: str
    agent_type: str = ""
    last_message: str = ""
    tasks: tuple[Task, ...] = ()


type News = Annotated[Busy | Idle | AgentStarted | AgentFinished, Field(discriminator="kind")]

NEWS: Final = TypeAdapter[News](News)


class _HookEvent(BaseModel):
    hook_event_name: str = ""
    background_tasks: tuple[Task, ...] = ()
    agent_id: str = ""
    agent_type: str = ""
    last_assistant_message: str | None = None


def _agent_news(hook: _HookEvent) -> AgentStarted | AgentFinished:
    if hook.hook_event_name == "SubagentStart":
        return AgentStarted(agent_id=hook.agent_id, agent_type=hook.agent_type)
    return AgentFinished(
        agent_id=hook.agent_id,
        agent_type=hook.agent_type,
        last_message=hook.last_assistant_message or "",
        tasks=hook.background_tasks,
    )


def news_of(event: str) -> News | None:
    try:
        hook = _HookEvent.model_validate_json(event)
    except ValidationError:
        return None
    match hook.hook_event_name:
        case "UserPromptSubmit":
            return Busy()
        case "Stop":
            return Busy(tasks=hook.background_tasks) if hook.background_tasks else Idle()
        case "StopFailure" | "SessionEnd":
            return Idle()
        case "SubagentStart" | "SubagentStop":
            return _agent_news(hook)
        case _:
            return None


def tell_bridge(path: Path, news: News) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SEND_TIMEOUT)
        try:
            connection.connect(str(path))
            connection.sendall(news.model_dump_json().encode() + b"\n")
        except OSError:
            return


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


def _log(news: News) -> None:
    match news:
        case Busy() | Idle():
            logger.info("Claude Code is %s", news.kind)
        case AgentStarted():
            logger.info("agent %s started, of type %r", news.agent_id, news.agent_type)
        case AgentFinished():
            logger.info("agent %s finished, of type %r", news.agent_id, news.agent_type)
        case _:
            assert_never(news)


async def listen_to_claude(path: Path, heard: Callable[[News], Awaitable[None]]) -> None:
    await anyio.Path(path).parent.mkdir(parents=True, exist_ok=True)
    await anyio.Path(path).unlink(missing_ok=True)

    async def handle(stream: SocketStream) -> None:
        news = await _read_news(stream)
        if news is None:
            return
        _log(news)
        await heard(news)

    async with await anyio.create_unix_listener(path) as listener:
        await listener.serve(handle)
