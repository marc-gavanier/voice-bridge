from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream
from mcp import ClientSession, types
from mcp.shared.memory import create_client_server_memory_streams
from mcp.shared.message import SessionMessage

from voice_bridge.features.conversation.implementations.claude_channel import (
    ReplyTool,
    channel_server,
    forward,
    initialization_options,
)

pytestmark = pytest.mark.anyio

TOOL = ReplyTool(description="Speak a reply aloud", text_description="The text to speak")


@dataclass(frozen=True)
class Connection:
    session: ClientSession
    replies: MemoryObjectReceiveStream[str]
    initialized: types.InitializeResult


@asynccontextmanager
async def connected() -> AsyncGenerator[Connection]:
    replies_in, replies_out = anyio.create_memory_object_stream[str](10)
    server = channel_server(instructions="Answer with reply.", tool=TOOL, replies=replies_in)
    async with (
        replies_in,
        replies_out,
        create_client_server_memory_streams() as (client_streams, server_streams),
        anyio.create_task_group() as tasks,
    ):
        _ = tasks.start_soon(server.run, server_streams[0], server_streams[1], initialization_options(server))
        async with ClientSession(client_streams[0], client_streams[1]) as session:
            yield Connection(session=session, replies=replies_out, initialized=await session.initialize())
        tasks.cancel_scope.cancel()


async def test_the_server_declares_itself_a_claude_channel() -> None:
    async with connected() as connection:
        capabilities = connection.initialized.capabilities
    assert capabilities.experimental == {"claude/channel": {}}


async def test_the_server_gives_its_instructions_to_claude() -> None:
    async with connected() as connection:
        instructions = connection.initialized.instructions
    assert instructions == "Answer with reply."


async def test_the_reply_tool_is_listed() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[0].name == "reply"


async def test_the_reply_tool_requires_a_text() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[0].input_schema["required"] == ["text"]


async def test_the_reply_tool_is_always_loaded() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[0].meta == {"anthropic/alwaysLoad": True}


async def test_calling_reply_hands_the_text_to_the_conversation() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("reply", {"text": "Bonjour."})
        reply = await connection.replies.receive()
    assert reply == "Bonjour."


async def test_calling_reply_confirms_the_text_was_sent() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("reply", {"text": "Bonjour."})
    assert result.content == [types.TextContent(type="text", text="sent")]


async def test_calling_an_unknown_tool_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("other", {})
    assert result.is_error


async def test_calling_reply_without_text_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("reply", {"words": "Bonjour."})
    assert result.is_error


async def notification(text: str, *, interrupted: bool) -> types.JSONRPCMessage:
    sent, received = anyio.create_memory_object_stream[SessionMessage](1)
    async with sent, received:
        await forward(sent, text, interrupted=interrupted)
        return (await received.receive()).message


async def test_forwarding_sends_a_claude_channel_notification() -> None:
    assert await notification("tu en es où", interrupted=False) == types.JSONRPCNotification(
        jsonrpc="2.0", method="notifications/claude/channel", params={"content": "tu en es où", "meta": {}}
    )


async def test_forwarding_an_interruption_flags_it() -> None:
    assert await notification("attends", interrupted=True) == types.JSONRPCNotification(
        jsonrpc="2.0",
        method="notifications/claude/channel",
        params={"content": "attends", "meta": {"interrupted": "true"}},
    )


@asynccontextmanager
async def discovered() -> AsyncGenerator[types.DiscoverResult]:
    replies_in, replies_out = anyio.create_memory_object_stream[str](10)
    server = channel_server(instructions="Answer with reply.", tool=TOOL, replies=replies_in)
    async with (
        replies_in,
        replies_out,
        create_client_server_memory_streams() as (client_streams, server_streams),
        anyio.create_task_group() as tasks,
    ):
        _ = tasks.start_soon(server.run, server_streams[0], server_streams[1], initialization_options(server))
        async with ClientSession(client_streams[0], client_streams[1]) as session:
            yield await session.discover()
        tasks.cancel_scope.cancel()


async def test_the_server_declares_itself_a_claude_channel_to_modern_clients() -> None:
    async with discovered() as discovery:
        capabilities = discovery.capabilities
    assert capabilities.experimental == {"claude/channel": {}}


async def test_the_server_still_offers_its_tools_to_modern_clients() -> None:
    async with discovered() as discovery:
        capabilities = discovery.capabilities
    assert capabilities.tools is not None


async def test_the_server_gives_its_instructions_to_modern_clients() -> None:
    async with discovered() as discovery:
        instructions = discovery.instructions
    assert instructions == "Answer with reply."
