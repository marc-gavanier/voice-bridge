import io
import json
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream
from mcp import ClientSession, types
from mcp.shared.memory import create_client_server_memory_streams
from mcp.shared.message import SessionMessage

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_channel import (
    BoardTool,
    ChannelTools,
    EndSessionTool,
    Forwarder,
    PlayTool,
    Reply,
    ReplyTool,
    channel_server,
    forward,
    initialization_options,
    serve_over_stdio,
)
from voice_bridge.features.conversation.domain.turn_taking import Recording

pytestmark = pytest.mark.anyio

TOOL = ReplyTool(
    description="Speak a reply aloud",
    text_description="The text to speak",
)
END_TOOL = EndSessionTool(description="Say goodbye and end the session", text_description="The goodbye to speak")
BOARD = '{"at_work": [], "finished": []}'


def board() -> str:
    return BOARD


BOARD_TOOL = BoardTool(description="Read the board of agents", read=board)
RECORDED = b"\x01\x00" * 480


async def read_clip(path: str) -> bytes:
    if path.endswith(".txt"):
        message = f"{path} is not an audio file"
        raise ValueError(message)
    return RECORDED


PLAY_TOOL = PlayTool(
    description="Play an audio file",
    path_description="The absolute path of the file",
    label_description="A few words said before it",
    read=read_clip,
)
TOOLS = ChannelTools(reply=TOOL, end_session=END_TOOL, board=BOARD_TOOL, play=PLAY_TOOL)


@dataclass(frozen=True)
class Connection:
    session: ClientSession
    replies: MemoryObjectReceiveStream[Reply]
    initialized: types.InitializeResult


@asynccontextmanager
async def connected() -> AsyncGenerator[Connection]:
    replies_in, replies_out = anyio.create_memory_object_stream[Reply](10)
    server = channel_server(
        instructions="Answer with reply.",
        tools=TOOLS,
        replies=replies_in,
    )
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


async def test_the_reply_tool_takes_only_the_text() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[0].input_schema["properties"] == {"text": {"type": "string", "description": "The text to speak"}}


async def test_the_reply_tool_is_always_loaded() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[0].meta == {"anthropic/alwaysLoad": True}


async def test_calling_reply_hands_the_text_to_the_conversation() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("reply", {"text": "Bonjour."})
        reply = await connection.replies.receive()
    assert reply == Reply(text="Bonjour.")


async def test_a_working_flag_from_former_instructions_is_ignored() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("reply", {"text": "Je regarde.", "working": True})
        reply = await connection.replies.receive()
    assert reply == Reply(text="Je regarde.")


async def test_calling_reply_confirms_the_text_was_sent() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("reply", {"text": "Bonjour."})
    assert result.content == [types.TextContent(type="text", text="sent")]


async def test_the_board_tool_is_listed_after_end_session() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert [tool.name for tool in tools.tools][:3] == ["reply", "end_session", "board"]


async def test_the_play_tool_is_listed_last() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[-1].name == "play"


async def test_the_play_tool_requires_a_path_and_takes_a_label_and_is_always_loaded() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert (tools.tools[3].description, tools.tools[3].input_schema, tools.tools[3].meta) == (
        "Play an audio file",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute path of the file"},
                "label": {"type": "string", "description": "A few words said before it"},
            },
            "required": ["path"],
        },
        {"anthropic/alwaysLoad": True},
    )


async def test_playing_a_file_hands_its_recording_and_label_to_the_conversation() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("play", {"path": "/clips/sample.wav", "label": "Écoute."})
        reply = await connection.replies.receive()
    assert reply == Reply(text="Écoute.", recording=Recording(name="sample.wav", pcm=RECORDED))


async def test_playing_a_file_without_a_label_says_nothing_before_it() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("play", {"path": "/clips/sample.wav"})
        reply = await connection.replies.receive()
    assert reply == Reply(text="", recording=Recording(name="sample.wav", pcm=RECORDED))


async def test_playing_a_file_confirms_it_was_sent() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("play", {"path": "/clips/sample.wav"})
    assert result.content == [types.TextContent(type="text", text="sent")]


async def test_playing_a_refused_file_tells_claude_why() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("play", {"path": "/clips/notes.txt"})
    assert (result.is_error, result.content) == (
        True,
        [types.TextContent(type="text", text="/clips/notes.txt is not an audio file")],
    )


async def test_playing_a_refused_file_hands_nothing_to_the_conversation() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("play", {"path": "/clips/notes.txt"})
        _ = await connection.session.call_tool("reply", {"text": "Bonjour."})
        reply = await connection.replies.receive()
    assert reply == Reply(text="Bonjour.")


async def test_a_refused_file_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with connected() as connection:
        _ = await connection.session.call_tool("play", {"path": "/clips/notes.txt"})
    assert "play refused: /clips/notes.txt is not an audio file" in caplog.text


async def test_a_played_file_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with connected() as connection:
        _ = await connection.session.call_tool("play", {"path": "/clips/sample.wav", "label": "Écoute."})
    assert "clip received from Claude: sample.wav, after 'Écoute.'" in caplog.text


async def test_playing_without_a_path_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("play", {"label": "Écoute."})
    assert result.is_error


async def test_the_board_tool_takes_nothing_and_is_always_loaded() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert (tools.tools[2].description, tools.tools[2].input_schema, tools.tools[2].meta) == (
        "Read the board of agents",
        {"type": "object", "properties": {}},
        {"anthropic/alwaysLoad": True},
    )


async def test_reading_the_board_gives_it_to_claude() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("board", {})
    assert result.content == [types.TextContent(type="text", text=BOARD)]


async def test_reading_the_board_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with connected() as connection:
        _ = await connection.session.call_tool("board", {})
    assert "board read by Claude" in caplog.text


async def test_the_end_session_tool_requires_a_goodbye() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert tools.tools[1].input_schema == {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The goodbye to speak"}},
        "required": ["text"],
    }


async def test_the_end_session_tool_is_always_loaded() -> None:
    async with connected() as connection:
        tools = await connection.session.list_tools()
    assert (tools.tools[1].description, tools.tools[1].meta) == (
        "Say goodbye and end the session",
        {"anthropic/alwaysLoad": True},
    )


async def test_ending_the_session_hands_the_goodbye_to_the_conversation() -> None:
    async with connected() as connection:
        _ = await connection.session.call_tool("end_session", {"text": "À demain."})
        reply = await connection.replies.receive()
    assert reply == Reply(text="À demain.", ending=True)


async def test_ending_the_session_confirms_the_goodbye_will_be_said() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("end_session", {"text": "À demain."})
    assert result.content == [types.TextContent(type="text", text="ending")]


async def test_ending_the_session_without_a_goodbye_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("end_session", {})
    assert result.is_error


async def test_calling_an_unknown_tool_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("other", {})
    assert result.is_error


async def test_calling_reply_without_text_is_an_error() -> None:
    async with connected() as connection:
        result = await connection.session.call_tool("reply", {"words": "Bonjour."})
    assert result.is_error


async def notification(text: str, *, interrupted: bool, acknowledgement: str | None = None) -> types.JSONRPCMessage:
    sent, received = anyio.create_memory_object_stream[SessionMessage](1)
    async with sent, received:
        await forward(sent, text, interrupted=interrupted, acknowledgement=acknowledgement)
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


async def test_forwarding_tells_the_acknowledgement_the_speaker_hears() -> None:
    assert await notification("tu en es où", interrupted=False, acknowledgement="Voyons.") == types.JSONRPCNotification(
        jsonrpc="2.0",
        method="notifications/claude/channel",
        params={"content": "tu en es où", "meta": {"acknowledgement": "Voyons."}},
    )


MODERN_DISCOVERY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "server/discover",
    "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}},
}
HANDSHAKE = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "initialize",
    "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "claude", "version": "0"}},
}


async def exchanged(*requests: Mapping[str, object]) -> list[types.JSONRPCMessage]:
    replies_in, replies_out = anyio.create_memory_object_stream[Reply](10)
    server = channel_server(
        instructions="Answer with reply.",
        tools=TOOLS,
        replies=replies_in,
    )
    written = io.StringIO()

    async def converse(claude: Forwarder) -> None:
        await claude("bonjour", interrupted=False, acknowledgement=None)

    async with replies_in, replies_out:
        await serve_over_stdio(
            server,
            converse,
            stdin=anyio.wrap_file(io.StringIO("".join(f"{json.dumps(request)}\n" for request in requests))),
            stdout=anyio.wrap_file(written),
        )
    return [types.jsonrpc_message_adapter.validate_json(line) for line in written.getvalue().splitlines()]


def handshake_result(messages: list[types.JSONRPCMessage]) -> types.InitializeResult:
    response = next(message for message in messages if isinstance(message, types.JSONRPCResponse))
    return types.InitializeResult.model_validate(response.result)


async def test_a_modern_discovery_is_refused_so_the_client_falls_back_to_the_handshake() -> None:
    assert types.JSONRPCError(
        jsonrpc="2.0", id=1, error=types.ErrorData(code=-32601, message="Method not found", data="server/discover")
    ) in await exchanged(MODERN_DISCOVERY, HANDSHAKE)


async def test_the_handshake_after_a_refused_discovery_declares_the_claude_channel() -> None:
    assert handshake_result(await exchanged(MODERN_DISCOVERY, HANDSHAKE)).capabilities.experimental == {
        "claude/channel": {}
    }


async def test_the_handshake_settles_on_a_protocol_with_channel_delivery() -> None:
    assert handshake_result(await exchanged(MODERN_DISCOVERY, HANDSHAKE)).protocol_version == "2025-11-25"


async def test_the_conversation_is_forwarded_as_a_channel_notification() -> None:
    assert types.JSONRPCNotification(
        jsonrpc="2.0", method="notifications/claude/channel", params={"content": "bonjour", "meta": {}}
    ) in await exchanged(HANDSHAKE)
