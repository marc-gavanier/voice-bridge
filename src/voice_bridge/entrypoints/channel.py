import logging
import math
import sys

import anyio
from mcp.server.stdio import stdio_server

from voice_bridge.configuration.language import LanguagePack, language_pack, load_instructions
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.logs import configure_logging
from voice_bridge.entrypoints.voice import converse
from voice_bridge.features.conversation.implementations.claude_channel import (
    ReplyTool,
    channel_server,
    forward,
    initialization_options,
)

logger = logging.getLogger(__name__)


async def serve(settings: Settings, language: LanguagePack) -> None:
    replies_in, replies_out = anyio.create_memory_object_stream[str](math.inf)
    server = channel_server(
        instructions=load_instructions(settings.instructions_file, default=language.instructions),
        tool=ReplyTool(description=language.reply_tool_description, text_description=language.reply_text_description),
        replies=replies_in,
    )
    async with replies_in, replies_out, stdio_server() as (read, write), anyio.create_task_group() as tasks:

        async def claude(text: str, *, interrupted: bool) -> None:
            logger.info("forwarded %r%s", text, " after an interruption" if interrupted else "")
            await forward(write, text, interrupted=interrupted)

        _ = tasks.start_soon(converse, settings, language, claude, replies_out, settings.mumble.username)
        await server.run(read, write, initialization_options(server))
        tasks.cancel_scope.cancel()


def main() -> None:
    settings = load_settings(config_file("Talk to this Claude Code session over Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file)
    anyio.run(serve, settings, language_pack(settings.language))
