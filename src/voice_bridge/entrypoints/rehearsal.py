import logging
import math
import sys
from datetime import datetime
from functools import partial
from typing import Final

import anyio

from voice_bridge.configuration.language import LanguagePack, language_pack
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs
from voice_bridge.entrypoints.logs import configure_logging, run_logged
from voice_bridge.entrypoints.telemetry import report_errors
from voice_bridge.entrypoints.voice import ClaudeSide, converse
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_channel import Reply
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard

USERNAME: Final = "rehearsal"

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now().astimezone()


async def rehearse(settings: Settings, language: LanguagePack) -> None:
    said_in, said_out = anyio.create_memory_object_stream[Reply](math.inf)
    async with said_in, said_out:

        async def repeat(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
            logger.info(
                "repeating %r%s, acknowledged with %r",
                text,
                " after an interruption" if interrupted else "",
                acknowledgement,
            )
            await said_in.send(Reply(text=text))

        side = ClaudeSide(claude=repeat, replies=said_out, board=WorkBoard(clock=now))
        await converse(settings, language, side, USERNAME)


def main() -> None:
    settings = load_settings(config_file("Repeat everything the speaker says, to test the voice path.", sys.argv[1:]))
    configure_logging(settings.log_file.with_name("rehearsal.log"))
    _ = report_errors()
    with watching_crashes(crash_file_of(settings.log_file.with_name("rehearsal.log"))) as watch:
        run_logged(
            watching_hangs, watch, settings.hang_after, partial(rehearse, settings, language_pack(settings.language))
        )
