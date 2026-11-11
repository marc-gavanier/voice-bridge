import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, assert_never

import anyio

from voice_bridge.features.conversation.domain.turn_taking import (
    Acknowledge,
    AwaitSilence,
    Command,
    Conversation,
    Event,
    Forward,
    Play,
    SilenceLasted,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    step,
)
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from anyio.abc import ObjectSendStream, TaskGroup

logger = logging.getLogger(__name__)


class Claude(Protocol):
    async def __call__(self, text: str, *, interrupted: bool) -> None: ...


class Acknowledgement(Protocol):
    def __call__(self, *, question: bool) -> tuple[str, bytes] | None: ...


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


async def _synthesize(mouth: Mouth, emit: ObjectSendStream[Event], order: Synthesize) -> None:
    started = mouth.clock()
    pcm = await mouth.voice(order.sentence)
    if pcm is None:
        await emit.send(SynthesisFailed(ticket=order.ticket))
        return
    spoken, ready = duration(pcm, mouth.rate), mouth.clock()
    logger.info("voice in %.2f s for %.1f s of speech: %r", ready - started, spoken, order.sentence)
    await emit.send(Synthesized(ticket=order.ticket, pcm=pcm, duration=spoken, at=ready))


def _acknowledge(mouth: Mouth, *, question: bool) -> None:
    clip = mouth.acknowledgement(question=question)
    if clip is None:
        return
    sentence, pcm = clip
    mouth.speaker.play(pcm)
    logger.info("acknowledged with %r", sentence)


async def _await_silence(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitSilence) -> None:
    await anyio.sleep(mouth.acknowledgement_delay)
    await emit.send(SilenceLasted(ticket=order.ticket))


async def _execute(mouth: Mouth, emit: ObjectSendStream[Event], tasks: TaskGroup, command: Command) -> None:
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
        case Acknowledge(question=question):
            _acknowledge(mouth, question=question)
        case Forward(text=text, interrupted=interrupted):
            await mouth.claude(text, interrupted=interrupted)
        case _:
            assert_never(command)


async def hold_conversation(mouth: Mouth, events: AsyncIterable[Event], emit: ObjectSendStream[Event]) -> None:
    state = Conversation()
    async with anyio.create_task_group() as tasks:
        async for event in events:
            state, commands = step(state, event)
            for command in commands:
                await _execute(mouth, emit, tasks, command)
        tasks.cancel_scope.cancel()
