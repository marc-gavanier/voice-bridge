import logging
import os
import signal
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import PurePath
from typing import TYPE_CHECKING, Final, Protocol

import anyio
from mcp import types
from mcp.server.lowlevel.server import Server
from mcp.server.runner import serve_loop
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage
from pydantic import BaseModel, ValidationError

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import AgentMessageChunk, Prompt
from voice_bridge.features.conversation.domain.turn_taking import Recording

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from anyio.abc import ObjectSendStream
    from mcp.server.context import ServerRequestContext
    from mcp.server.models import InitializationOptions

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import SessionUpdate
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Assistant

SERVER_NAME: Final = "voice"
TOOL_NAME: Final = "reply"
END_TOOL_NAME: Final = "end_session"
BOARD_TOOL_NAME: Final = "board"
PLAY_TOOL_NAME: Final = "play"
ALWAYS_LOAD: Final = {"anthropic/alwaysLoad": True}
CHANNEL_CAPABILITY: Final = "claude/channel"
CHANNEL_NOTIFICATION: Final = "notifications/claude/channel"

logger = logging.getLogger(__name__)


class MessageSender(Protocol):
    async def send(self, item: SessionMessage, /) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyTool:
    description: str
    text_description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EndSessionTool:
    description: str
    text_description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BoardTool:
    description: str
    read: Callable[[], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayTool:
    description: str
    path_description: str
    label_description: str
    read: Callable[[str], Awaitable[bytes]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ChannelTools:
    reply: ReplyTool
    end_session: EndSessionTool
    board: BoardTool
    play: PlayTool


class ReplyArguments(BaseModel):
    text: str


class EndSessionArguments(BaseModel):
    text: str


class PlayArguments(BaseModel):
    path: str
    label: str = ""


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


def _end_session_tool(tool: EndSessionTool) -> types.Tool:
    return types.Tool.model_validate(
        {
            "name": END_TOOL_NAME,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": tool.text_description}},
                "required": ["text"],
            },
            "_meta": ALWAYS_LOAD,
        }
    )


def _board_tool(tool: BoardTool) -> types.Tool:
    return types.Tool.model_validate(
        {
            "name": BOARD_TOOL_NAME,
            "description": tool.description,
            "inputSchema": {"type": "object", "properties": {}},
            "_meta": ALWAYS_LOAD,
        }
    )


def _play_tool(tool: PlayTool) -> types.Tool:
    return types.Tool.model_validate(
        {
            "name": PLAY_TOOL_NAME,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": tool.path_description},
                    "label": {"type": "string", "description": tool.label_description},
                },
                "required": ["path"],
            },
            "_meta": ALWAYS_LOAD,
        }
    )


async def _clip_of(tool: PlayTool, arguments: dict[str, object]) -> AgentMessageChunk | types.CallToolResult:
    try:
        asked = PlayArguments.model_validate(arguments)
    except ValidationError as error:
        return _error(str(error))
    try:
        pcm = await tool.read(asked.path)
    except ValueError as error:
        logger.info("play refused: %s", error)
        return _error(str(error))
    name = PurePath(asked.path).name
    logger.info("clip received from Claude: %s, after %r", name, asked.label)
    return AgentMessageChunk(text=asked.label, recording=Recording(name=name, pcm=pcm))


def _board(tool: BoardTool) -> types.CallToolResult:
    logger.info("board read by Claude")
    return types.CallToolResult(content=[types.TextContent(type="text", text=tool.read())])


def _reply_of(name: str, arguments: dict[str, object]) -> AgentMessageChunk | types.CallToolResult:
    try:
        if name == END_TOOL_NAME:
            return AgentMessageChunk(text=EndSessionArguments.model_validate(arguments).text, closing=True)
        reply = ReplyArguments.model_validate(arguments)
    except ValidationError as error:
        return _error(str(error))
    return AgentMessageChunk(text=reply.text)


def _logged(reply: AgentMessageChunk | types.CallToolResult) -> AgentMessageChunk | types.CallToolResult:
    if isinstance(reply, types.CallToolResult):
        return reply
    if reply.closing:
        logger.info("goodbye received from Claude: %r, the session ends after it", reply.text)
    else:
        logger.info("reply received from Claude: %r", reply.text)
    return reply


async def _received(
    tools: ChannelTools, params: types.CallToolRequestParams
) -> AgentMessageChunk | types.CallToolResult:
    arguments = params.arguments or {}
    if params.name == PLAY_TOOL_NAME:
        return await _clip_of(tools.play, arguments)
    if params.name in {TOOL_NAME, END_TOOL_NAME}:
        return _logged(_reply_of(params.name, arguments))
    return _error(f"unknown tool: {params.name}")


def channel_server(
    *, instructions: str, tools: ChannelTools, updates: ObjectSendStream[SessionUpdate]
) -> Server[object]:
    reply = types.Tool.model_validate(
        {
            "name": TOOL_NAME,
            "description": tools.reply.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": tools.reply.text_description},
                },
                "required": ["text"],
            },
            "_meta": ALWAYS_LOAD,
        }
    )
    listed = [reply, _end_session_tool(tools.end_session), _board_tool(tools.board), _play_tool(tools.play)]

    async def list_tools(
        _context: ServerRequestContext[object], _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=listed)

    async def call_tool(
        _context: ServerRequestContext[object], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        if params.name == BOARD_TOOL_NAME:
            return _board(tools.board)
        received = await _received(tools, params)
        if isinstance(received, types.CallToolResult):
            return received
        await updates.send(received)
        answer = "ending" if received.closing else "sent"
        return types.CallToolResult(content=[types.TextContent(type="text", text=answer)])

    return Server(
        SERVER_NAME,
        version=version("voice-bridge"),
        instructions=instructions,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def initialization_options(server: Server[object]) -> InitializationOptions:
    return server.create_initialization_options(experimental_capabilities={CHANNEL_CAPABILITY: {}})


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaudeCode:
    write: MessageSender
    pid: int | None

    async def prompt(self, prompt: Prompt) -> None:
        await forward(self.write, prompt)

    async def close(self) -> None:
        if self.pid is None:
            logger.warning("no Claude Code process to end: start the bridge with scripts/claude-voice.sh")
            return
        logger.info("ending Claude Code, process %d", self.pid)
        os.kill(self.pid, signal.SIGTERM)


async def serve_over_stdio(
    server: Server[object],
    converse: Callable[[Assistant], Coroutine[object, object, None]],
    *,
    pid: int | None,
    stdin: anyio.AsyncFile[str] | None = None,
    stdout: anyio.AsyncFile[str] | None = None,
) -> None:
    async with stdio_server(stdin, stdout) as (read, write), anyio.create_task_group() as tasks:
        _ = tasks.start_soon(converse, ClaudeCode(write=write, pid=pid))
        async with server.lifespan(server) as state:
            await serve_loop(server, read, write, lifespan_state=state, init_options=initialization_options(server))
        tasks.cancel_scope.cancel()


async def forward(write: MessageSender, prompt: Prompt) -> None:
    meta = {"interrupted": "true"} if prompt.interrupted else {}
    if prompt.acknowledgement is not None:
        meta["acknowledgement"] = prompt.acknowledgement
    notification = types.JSONRPCNotification(
        jsonrpc="2.0", method=CHANNEL_NOTIFICATION, params={"content": prompt.text, "meta": meta}
    )
    await write.send(SessionMessage(notification))
