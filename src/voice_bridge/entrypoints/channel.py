import logging
import math
import sys
from datetime import datetime
from functools import partial

import anyio

from voice_bridge.configuration.language import LanguagePack, language_pack, load_instructions
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs
from voice_bridge.entrypoints.logs import configure_logging, run_logged
from voice_bridge.entrypoints.telemetry import report_errors
from voice_bridge.entrypoints.voice import ClaudeSide, converse
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_channel import (
    BoardTool,
    EndSessionTool,
    Forwarder,
    Reply,
    ReplyTool,
    channel_server,
    serve_over_stdio,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now().astimezone()


async def serve(settings: Settings, language: LanguagePack) -> None:
    replies_in, replies_out = anyio.create_memory_object_stream[Reply](math.inf)
    board = WorkBoard(clock=now)
    server = channel_server(
        instructions=load_instructions(settings.instructions_file, default=language.instructions),
        tool=ReplyTool(
            description=language.reply_tool_description,
            text_description=language.reply_text_description,
        ),
        end_tool=EndSessionTool(
            description=language.end_tool_description, text_description=language.end_text_description
        ),
        board_tool=BoardTool(description=language.board_tool_description, read=board.report),
        replies=replies_in,
    )
    async with replies_in, replies_out:

        async def talk_to(claude: Forwarder) -> None:
            async def logged(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
                logger.info(
                    "forwarded %r%s, acknowledged with %r",
                    text,
                    " after an interruption" if interrupted else "",
                    acknowledgement,
                )
                await claude(text, interrupted=interrupted, acknowledgement=acknowledgement)

            side = ClaudeSide(claude=logged, replies=replies_out, board=board)
            await converse(settings, language, side, settings.mumble.username)

        await serve_over_stdio(server, talk_to)


def main() -> None:
    settings = load_settings(config_file("Talk to this Claude Code session over Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file, settings.logging)
    _ = report_errors()
    with watching_crashes(crash_file_of(settings.log_file)) as watch:
        run_logged(
            watching_hangs, watch, settings.hang_after, partial(serve, settings, language_pack(settings.language))
        )
