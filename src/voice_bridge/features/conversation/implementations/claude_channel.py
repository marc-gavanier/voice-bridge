from dataclasses import dataclass
from importlib.metadata import version
from typing import TYPE_CHECKING, Final, Protocol

import anyio
from mcp import types
from mcp.server.lowlevel.server import Server
from mcp.server.runner import serve_loop
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from anyio.abc import ObjectSendStream
    from mcp.server.context import ServerRequestContext
    from mcp.server.models import InitializationOptions

SERVER_NAME: Final = "voice"
TOOL_NAME: Final = "reply"
CHANNEL_CAPABILITY: Final = "claude/channel"
CHANNEL_NOTIFICATION: Final = "notifications/claude/channel"


class MessageSender(Protocol):
    async def send(self, item: SessionMessage, /) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplyTool:
    description: str
    text_description: str


class ReplyArguments(BaseModel):
    text: str


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


def channel_server(*, instructions: str, tool: ReplyTool, replies: ObjectSendStream[str]) -> Server[object]:
    reply = types.Tool.model_validate(
        {
            "name": TOOL_NAME,
            "description": tool.description,
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": tool.text_description}},
                "required": ["text"],
            },
            "_meta": {"anthropic/alwaysLoad": True},
        }
    )

    async def list_tools(
        _context: ServerRequestContext[object], _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[reply])

    async def call_tool(
        _context: ServerRequestContext[object], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        if params.name != TOOL_NAME:
            return _error(f"unknown tool: {params.name}")
        try:
            arguments = ReplyArguments.model_validate(params.arguments or {})
        except ValidationError as error:
            return _error(str(error))
        await replies.send(arguments.text)
        return types.CallToolResult(content=[types.TextContent(type="text", text="sent")])

    return Server(
        SERVER_NAME,
        version=version("voice-bridge"),
        instructions=instructions,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def initialization_options(server: Server[object]) -> InitializationOptions:
    return server.create_initialization_options(experimental_capabilities={CHANNEL_CAPABILITY: {}})


class Forwarder(Protocol):
    async def __call__(self, text: str, *, interrupted: bool) -> None: ...


async def serve_over_stdio(
    server: Server[object],
    converse: Callable[[Forwarder], Coroutine[object, object, None]],
    *,
    stdin: anyio.AsyncFile[str] | None = None,
    stdout: anyio.AsyncFile[str] | None = None,
) -> None:
    async with stdio_server(stdin, stdout) as (read, write), anyio.create_task_group() as tasks:

        async def claude(text: str, *, interrupted: bool) -> None:
            await forward(write, text, interrupted=interrupted)

        _ = tasks.start_soon(converse, claude)
        async with server.lifespan(server) as state:
            await serve_loop(server, read, write, lifespan_state=state, init_options=initialization_options(server))
        tasks.cancel_scope.cancel()


async def forward(write: MessageSender, text: str, *, interrupted: bool) -> None:
    meta = {"interrupted": "true"} if interrupted else {}
    notification = types.JSONRPCNotification(
        jsonrpc="2.0", method=CHANNEL_NOTIFICATION, params={"content": text, "meta": meta}
    )
    await write.send(SessionMessage(notification))
