import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

import anyio
import httpx

from voice_bridge.configuration.language import LanguagePack, language_pack, load_instructions
from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs
from voice_bridge.entrypoints.logs import configure_logging, run_logged
from voice_bridge.entrypoints.telemetry import report_errors
from voice_bridge.entrypoints.voice import AssistantSide, audio_source, converse, mumble
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
from voice_bridge.features.speaking.abilities.play_clip.implementation.clip_file import check_clip
from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import health_answers

if TYPE_CHECKING:
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import Prompt
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Assistant

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now().astimezone()


def _play_tool(settings: Settings, language: LanguagePack, rate: int) -> PlayTool:
    source = audio_source(settings.clips.source, rate)

    async def check(path: str) -> None:
        await anyio.to_thread.run_sync(partial(check_clip, path, source=source))

    directories = ", ".join(str(directory) for directory in settings.clips.source.folder.directories)
    return PlayTool(
        description=language.play_tool_description,
        path_description=language.play_path_description.format(directories=directories),
        label_description=language.play_label_description,
        check=check,
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
    transport = mumble(settings, settings.transport.mumble.username)
    speech = httpx.AsyncClient(base_url=str(settings.speech_synthesis.openai.url))
    server = channel_server(
        instructions=load_instructions(settings.assistant.claude_code.instructions_file, default=language.instructions),
        tools=ChannelTools(
            reply=ReplyTool(
                description=language.reply_tool_description,
                text_description=language.reply_text_description,
                voice_ready=partial(health_answers, speech, settings.speech_synthesis.openai.health),
            ),
            end_session=EndSessionTool(
                description=language.end_tool_description, text_description=language.end_text_description
            ),
            board=BoardTool(description=language.board_tool_description, read=board.report),
            play=_play_tool(settings, language, transport.rate),
        ),
        updates=updates_in,
    )
    async with updates_in, updates_out, speech:

        async def talk_to(claude_code: Assistant) -> None:
            side = AssistantSide(
                assistant=_Logged(assistant=claude_code, board=board), updates=updates_out, board=board
            )
            async with anyio.create_task_group() as tasks:
                _ = tasks.start_soon(listen_to_claude, settings.assistant.claude_code.activity_socket, updates_in.send)
                await converse(settings, language, side, transport)
                tasks.cancel_scope.cancel()

        await serve_over_stdio(server, talk_to, pid=settings.assistant.claude_code.claude_pid)


def main() -> None:
    settings = load_settings(config_file("Talk to this Claude Code session over Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file, settings.log_retention, settings.logging)
    _ = report_errors()
    with watching_crashes(crash_file_of(settings.log_file)) as watch:
        run_logged(
            watching_hangs, watch, settings.hang_after, partial(serve, settings, language_pack(settings.language))
        )
