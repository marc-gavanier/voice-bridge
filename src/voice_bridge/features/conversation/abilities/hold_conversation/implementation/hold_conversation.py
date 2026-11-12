import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

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
    Leave,
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

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import (
        Acknowledgement,
        Claude,
        Speaker,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Mouth:
    voice: Callable[[str], Awaitable[bytes | None]]
    speaker: Speaker
    claude: Claude
    rate: int
    clock: Callable[[], float]
    acknowledgement: Acknowledgement
    settle: float
    hold_music: Callable[[], Awaitable[None]] | None
    hold_music_delay: float
    leave: Callable[[], Awaitable[None]]


@dataclass(slots=True)
class _Playback:
    scopes: list[anyio.CancelScope] = field(default_factory=list)
    acknowledgement: tuple[str, bytes] | None = None


async def _synthesize(mouth: Mouth, emit: ObjectSendStream[Event], order: Synthesize) -> None:
    started = mouth.clock()
    pcm = await mouth.voice(order.sentence)
    if pcm is None:
        await emit.send(SynthesisFailed(ticket=order.ticket))
        return
    spoken, ready = duration(pcm, mouth.rate), mouth.clock()
    logger.info("voice in %.2f s for %.1f s of speech: %r", ready - started, spoken, order.sentence)
    await emit.send(Synthesized(ticket=order.ticket, pcm=pcm, duration=spoken, at=ready))


async def _forward(mouth: Mouth, playback: _Playback, command: Forward) -> None:
    if command.pieces > 1:
        logger.info("joined %d pieces said with pauses", command.pieces)
    playback.acknowledgement = mouth.acknowledgement(command.text) if command.acknowledging else None
    sentence = playback.acknowledgement[0] if playback.acknowledgement else None
    await mouth.claude(command.text, interrupted=command.interrupted, acknowledgement=sentence)


def _acknowledge(mouth: Mouth, playback: _Playback) -> None:
    clip, playback.acknowledgement = playback.acknowledgement, None
    if clip is None:
        return
    sentence, pcm = clip
    mouth.speaker.play(pcm)
    logger.info("acknowledged with %r", sentence)


async def _await_silence(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitSilence) -> None:
    elapsed = 0.0 if order.since is None else mouth.clock() - order.since
    await anyio.sleep(max(0.0, mouth.settle - elapsed))
    await emit.send(SilenceLasted(ticket=order.ticket, at=mouth.clock()))


async def _await_hold(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitHold) -> None:
    await anyio.sleep(order.after + mouth.hold_music_delay)
    await emit.send(HoldLasted(ticket=order.ticket))


async def _leave(mouth: Mouth, order: Leave) -> None:
    await anyio.sleep(max(0.0, order.until - mouth.clock()))
    logger.info("leaving: the goodbye has been said")
    await mouth.leave()


async def _play_music(
    hold_music: Callable[[], Awaitable[None]], playback: _Playback, *, task_status: TaskStatus[None]
) -> None:
    with anyio.CancelScope() as scope:
        playback.scopes.append(scope)
        task_status.started()
        await hold_music()


async def _start_music(mouth: Mouth, playback: _Playback, tasks: TaskGroup) -> None:
    if mouth.hold_music is not None:
        await tasks.start(_play_music, mouth.hold_music, playback)


def _stop_music(mouth: Mouth, playback: _Playback) -> None:
    if not playback.scopes:
        return
    for scope in playback.scopes:
        scope.cancel()
    playback.scopes.clear()
    mouth.speaker.stop()
    logger.info("hold music stopped")


async def _later(
    mouth: Mouth, emit: ObjectSendStream[Event], command: Synthesize | AwaitSilence | AwaitHold | Leave
) -> None:
    match command:
        case Synthesize():
            await _synthesize(mouth, emit, command)
        case AwaitSilence():
            await _await_silence(mouth, emit, command)
        case AwaitHold():
            await _await_hold(mouth, emit, command)
        case Leave():
            await _leave(mouth, command)
        case _:
            assert_never(command)


async def _execute(
    mouth: Mouth, emit: ObjectSendStream[Event], tasks: TaskGroup, playback: _Playback, command: Command
) -> None:
    match command:
        case Synthesize() | AwaitSilence() | AwaitHold() | Leave():
            _ = tasks.start_soon(_later, mouth, emit, command)
        case Play(pcm=pcm):
            mouth.speaker.play(pcm)
        case StopPlaying(heard_at=heard_at):
            mouth.speaker.stop()
            logger.info(
                "interrupted, playback stopped %.0f ms after the voice was heard", (mouth.clock() - heard_at) * 1000
            )
        case Acknowledge():
            _acknowledge(mouth, playback)
        case StartHoldMusic():
            await _start_music(mouth, playback, tasks)
        case StopHoldMusic():
            _stop_music(mouth, playback)
        case Forward():
            await _forward(mouth, playback, command)
        case _:
            assert_never(command)


async def hold_conversation(mouth: Mouth, events: AsyncIterable[Event], emit: ObjectSendStream[Event]) -> None:
    state, playback = Conversation(), _Playback()
    async with anyio.create_task_group() as tasks:
        async for event in events:
            state, commands = step(state, event)
            for command in commands:
                await _execute(mouth, emit, tasks, playback, command)
        tasks.cancel_scope.cancel()
