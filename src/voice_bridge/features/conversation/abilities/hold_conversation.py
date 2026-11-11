import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, assert_never

import anyio

from voice_bridge.features.conversation.domain.turn_taking import (
    Acknowledge,
    AwaitHold,
    AwaitSilence,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    Play,
    SilenceLasted,
    StartHoldMusic,
    StopHoldMusic,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    step,
)
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from anyio.abc import ObjectSendStream, TaskGroup, TaskStatus

logger = logging.getLogger(__name__)


class Claude(Protocol):
    async def __call__(self, text: str, *, interrupted: bool) -> None: ...


class Acknowledgement(Protocol):
    def __call__(self, words: str) -> tuple[str, bytes] | None: ...


class Speaker(Protocol):
    def play(self, pcm: bytes) -> None: ...
    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Mouth:
    voice: Callable[[str], Awaitable[bytes | None]]
    speaker: Speaker
    claude: Claude
    rate: int
    clock: Callable[[], float]
    acknowledgement: Acknowledgement
    acknowledgement_delay: float
    hold_music: Callable[[], Awaitable[None]] | None
    hold_music_delay: float


@dataclass(slots=True)
class _Music:
    scopes: list[anyio.CancelScope] = field(default_factory=list)


async def _synthesize(mouth: Mouth, emit: ObjectSendStream[Event], order: Synthesize) -> None:
    started = mouth.clock()
    pcm = await mouth.voice(order.sentence)
    if pcm is None:
        await emit.send(SynthesisFailed(ticket=order.ticket))
        return
    spoken, ready = duration(pcm, mouth.rate), mouth.clock()
    logger.info("voice in %.2f s for %.1f s of speech: %r", ready - started, spoken, order.sentence)
    await emit.send(Synthesized(ticket=order.ticket, pcm=pcm, duration=spoken, at=ready))


def _acknowledge(mouth: Mouth, words: str) -> None:
    clip = mouth.acknowledgement(words)
    if clip is None:
        return
    sentence, pcm = clip
    mouth.speaker.play(pcm)
    logger.info("acknowledged with %r", sentence)


async def _await_silence(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitSilence) -> None:
    await anyio.sleep(mouth.acknowledgement_delay)
    await emit.send(SilenceLasted(ticket=order.ticket, at=mouth.clock()))


async def _await_hold(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitHold) -> None:
    await anyio.sleep(mouth.hold_music_delay)
    await emit.send(HoldLasted(ticket=order.ticket))


async def _play_music(
    hold_music: Callable[[], Awaitable[None]], music: _Music, *, task_status: TaskStatus[None]
) -> None:
    with anyio.CancelScope() as scope:
        music.scopes.append(scope)
        task_status.started()
        await hold_music()


async def _start_music(mouth: Mouth, music: _Music, tasks: TaskGroup) -> None:
    if mouth.hold_music is not None:
        await tasks.start(_play_music, mouth.hold_music, music)


def _stop_music(mouth: Mouth, music: _Music) -> None:
    if not music.scopes:
        return
    for scope in music.scopes:
        scope.cancel()
    music.scopes.clear()
    mouth.speaker.stop()
    logger.info("hold music stopped")


async def _execute(
    mouth: Mouth, emit: ObjectSendStream[Event], tasks: TaskGroup, music: _Music, command: Command
) -> None:
    match command:
        case Synthesize():
            _ = tasks.start_soon(_synthesize, mouth, emit, command)
        case Play(pcm=pcm):
            mouth.speaker.play(pcm)
        case StopPlaying(heard_at=heard_at):
            mouth.speaker.stop()
            logger.info(
                "interrupted, playback stopped %.0f ms after the voice was heard", (mouth.clock() - heard_at) * 1000
            )
        case AwaitSilence():
            _ = tasks.start_soon(_await_silence, mouth, emit, command)
        case Acknowledge(words=words):
            _acknowledge(mouth, words)
        case AwaitHold():
            _ = tasks.start_soon(_await_hold, mouth, emit, command)
        case StartHoldMusic():
            await _start_music(mouth, music, tasks)
        case StopHoldMusic():
            _stop_music(mouth, music)
        case Forward(text=text, interrupted=interrupted):
            await mouth.claude(text, interrupted=interrupted)
        case _:
            assert_never(command)


async def hold_conversation(mouth: Mouth, events: AsyncIterable[Event], emit: ObjectSendStream[Event]) -> None:
    state, music = Conversation(), _Music()
    async with anyio.create_task_group() as tasks:
        async for event in events:
            state, commands = step(state, event)
            for command in commands:
                await _execute(mouth, emit, tasks, music, command)
        tasks.cancel_scope.cancel()
