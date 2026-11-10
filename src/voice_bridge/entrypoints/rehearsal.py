import logging
import math
import sys
from typing import Final

import anyio

from voice_bridge.configuration.language import LanguagePack, language_pack
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.logs import configure_logging
from voice_bridge.entrypoints.voice import converse

USERNAME: Final = "rehearsal"

logger = logging.getLogger(__name__)


async def rehearse(settings: Settings, language: LanguagePack) -> None:
    said_in, said_out = anyio.create_memory_object_stream[str](math.inf)
    async with said_in, said_out:

        async def repeat(text: str, *, interrupted: bool) -> None:
            logger.info("repeating %r%s", text, " after an interruption" if interrupted else "")
            await said_in.send(text)

        await converse(settings, language, repeat, said_out, USERNAME)


def main() -> None:
    settings = load_settings(config_file("Repeat everything the speaker says, to test the voice path.", sys.argv[1:]))
    configure_logging(settings.log_file.with_name("rehearsal.log"))
    anyio.run(rehearse, settings, language_pack(settings.language))
