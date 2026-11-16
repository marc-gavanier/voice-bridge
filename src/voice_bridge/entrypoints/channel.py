import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

import anyio

from voice_bridge.configuration.language import LanguagePack, language_pack, load_instructions
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs
from voice_bridge.entrypoints.logs import configure_logging, run_logged
from voice_bridge.entrypoints.telemetry import report_errors
from voice_bridge.entrypoints.voice import AssistantSide, converse, mumble
from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import SessionUpdate
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    listen_to_claude,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_channel import (
    BoardTool,
    ChannelTools,
    EndSessionTool,
    PlayTool,
    ReplyTool,
    channel_server,
    serve_over_stdio,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard
from voice_bridge.features.speaking.abilities.play_clip.implementation.clip_file import ClipRules, read_clip
from voice_bridge.libraries.audio.file import decode_audio

if TYPE_CHECKING:
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import Prompt
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Assistant

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now().astimezone()


def _play_tool(settings: Settings, language: LanguagePack, rate: int) -> PlayTool:
    clips = settings.clips
    rules = ClipRules(directory=clips.directory, largest=clips.largest, longest=clips.longest, volume=clips.volume)

    async def read(path: str) -> bytes:
        return await anyio.to_thread.run_sync(partial(read_clip, path, rules=rules, rate=rate, decode=decode_audio))

    return PlayTool(
        description=language.play_tool_description,
        path_description=language.play_path_description.format(directory=clips.directory),
        label_description=language.play_label_description,
        read=read,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _Logged:
    assistant: Assistant
    board: WorkBoard

    async def prompt(self, prompt: Prompt) -> None:
        logger.info(
            "forwarded %r%s, acknowledged with %r",
            prompt.text,
            " after an interruption" if prompt.interrupted else "",
            prompt.acknowledgement,
        )
        self.board.forwarded()
        await self.assistant.prompt(prompt)

    async def close(self) -> None:
        await self.assistant.close()


async def serve(settings: Settings, language: LanguagePack) -> None:
    updates_in, updates_out = anyio.create_memory_object_stream[SessionUpdate](math.inf)
    board = WorkBoard(clock=now)
    transport = mumble(settings, settings.mumble.username)
    server = channel_server(
        instructions=load_instructions(settings.instructions_file, default=language.instructions),
        tools=ChannelTools(
            reply=ReplyTool(
                description=language.reply_tool_description,
                text_description=language.reply_text_description,
            ),
            end_session=EndSessionTool(
                description=language.end_tool_description, text_description=language.end_text_description
            ),
            board=BoardTool(description=language.board_tool_description, read=board.report),
            play=_play_tool(settings, language, transport.rate),
        ),
        updates=updates_in,
    )
    async with updates_in, updates_out:

        async def talk_to(claude_code: Assistant) -> None:
            side = AssistantSide(
                assistant=_Logged(assistant=claude_code, board=board), updates=updates_out, board=board
            )
            async with anyio.create_task_group() as tasks:
                _ = tasks.start_soon(listen_to_claude, settings.activity_socket, updates_in.send)
                await converse(settings, language, side, transport)
                tasks.cancel_scope.cancel()

        await serve_over_stdio(server, talk_to, pid=settings.claude_pid)


def main() -> None:
    settings = load_settings(config_file("Talk to this Claude Code session over Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file, settings.log_retention, settings.logging)
    _ = report_errors()
    with watching_crashes(crash_file_of(settings.log_file)) as watch:
        run_logged(
            watching_hangs, watch, settings.hang_after, partial(serve, settings, language_pack(settings.language))
        )
