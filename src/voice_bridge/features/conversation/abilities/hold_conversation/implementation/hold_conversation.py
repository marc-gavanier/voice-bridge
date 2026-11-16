import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

import anyio

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import Prompt
from voice_bridge.features.conversation.domain.turn_taking import (
    Acknowledge,
    Announce,
    AnswerLasted,
    AwaitAnswer,
    AwaitHold,
    AwaitSilence,
    CancelSynthesis,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    Leave,
    Play,
    Recording,
    Said,
    SilenceLasted,
    StartHoldMusic,
    StopHoldMusic,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Voiced,
    step,
)
from voice_bridge.features.conversation.domain.turn_trace import Acknowledged, Trace, close, forwarded, observe
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from anyio.abc import ObjectSendStream, TaskGroup, TaskStatus

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import (
        Acknowledgement,
        Announcement,
        Assistant,
        HoldMusic,
        Interpreter,
        Speaker,
        Telemetry,
        Voice,
    )
    from voice_bridge.features.conversation.domain.turn_trace import Report

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Mouth:
    voice: Voice
    speaker: Speaker
    assistant: Assistant
    rate: int
    clock: Callable[[], float]
    acknowledgement: Acknowledgement
    understood: Interpreter
    announcement: Announcement
    settle: float
    hold_music: HoldMusic | None
    hold_music_delay: float
    unanswered: tuple[str, ...]
    unanswered_after: float
    telemetry: Telemetry


@dataclass(slots=True)
class _Shell:
    scopes: list[anyio.CancelScope] = field(default_factory=list)
    syntheses: dict[int, anyio.CancelScope] = field(default_factory=dict)
    acknowledgement: tuple[str, bytes] | None = None
    trace: Trace = field(default_factory=Trace)


async def _voiced(mouth: Mouth, said: Said, hear: Callable[[bytes], Awaitable[None]]) -> bool:
    if isinstance(said, Recording):
        await hear(said.pcm)
        return True
    return await mouth.voice(said, hear)


@dataclass(slots=True)
class _Voicing:
    started: float
    first: float | None = None
    spoken: float = 0.0


async def _synthesize(mouth: Mouth, emit: ObjectSendStream[Event], order: Synthesize) -> None:
    voicing = _Voicing(started=mouth.clock())

    async def hear(pcm: bytes) -> None:
        at, lasting = mouth.clock(), duration(pcm, mouth.rate)
        if voicing.first is None:
            voicing.first = at
            logger.info("first audio in %.2f s: %r", at - voicing.started, order.sentence)
        voicing.spoken += lasting
        await emit.send(Voiced(ticket=order.ticket, pcm=pcm, duration=lasting, at=at))

    if not await _voiced(mouth, order.sentence, hear):
        await emit.send(SynthesisFailed(ticket=order.ticket))
        return
    ready = mouth.clock()
    logger.info("voice in %.2f s for %.1f s of speech: %r", ready - voicing.started, voicing.spoken, order.sentence)
    await emit.send(Synthesized(ticket=order.ticket, at=ready))


async def _synthesize_within(
    mouth: Mouth, emit: ObjectSendStream[Event], shell: _Shell, order: Synthesize, scope: anyio.CancelScope
) -> None:
    try:
        with scope:
            await _synthesize(mouth, emit, order)
    finally:
        _ = shell.syntheses.pop(order.ticket, None)


def _start_synthesis(
    mouth: Mouth, emit: ObjectSendStream[Event], tasks: TaskGroup, shell: _Shell, order: Synthesize
) -> None:
    scope = anyio.CancelScope()
    shell.syntheses[order.ticket] = scope
    _ = tasks.start_soon(_synthesize_within, mouth, emit, shell, order, scope)


def _cancel_synthesis(shell: _Shell, order: CancelSynthesis) -> None:
    shell.syntheses.pop(order.ticket, anyio.CancelScope()).cancel()
    logger.info("synthesis %d cancelled", order.ticket)


async def _forward(mouth: Mouth, shell: _Shell, command: Forward) -> None:
    if command.pieces > 1:
        logger.info("joined %d pieces said with pauses", command.pieces)
    shell.acknowledgement = mouth.acknowledgement(command.text) if command.acknowledging else None
    sentence = shell.acknowledgement[0] if shell.acknowledgement else None
    mouth.telemetry(forwarded(shell.trace, mouth.clock(), command, mouth.understood(command.text), sentence))
    await mouth.assistant.prompt(Prompt(text=command.text, interrupted=command.interrupted, acknowledgement=sentence))


def _acknowledge(mouth: Mouth, shell: _Shell, order: Acknowledge) -> None:
    clip, shell.acknowledgement = shell.acknowledgement, None
    if clip is None:
        return
    sentence, pcm = clip
    mouth.speaker.play(pcm)
    mouth.telemetry(Acknowledged(sentence=sentence, words=order.words, at=mouth.clock()))
    logger.info("acknowledged with %r", sentence)


def _announce(mouth: Mouth, order: Announce) -> None:
    clip = mouth.announcement(order.at_work)
    if clip is None:
        logger.info("no announcement ready for %d agents at work", order.at_work)
        return
    sentence, pcm = clip
    mouth.speaker.play(pcm)
    logger.info("announced %r", sentence)


async def _await_silence(mouth: Mouth, emit: ObjectSendStream[Event], order: AwaitSilence) -> None:
    wait = order.lasting if order.until is None else order.until - mouth.clock()
    await anyio.sleep(max(0.0, wait))
    await emit.send(SilenceLasted(ticket=order.ticket, at=mouth.clock()))


async def _await_hold(emit: ObjectSendStream[Event], order: AwaitHold) -> None:
    await anyio.sleep(order.after)
    await emit.send(HoldLasted(ticket=order.ticket))


async def _await_answer(emit: ObjectSendStream[Event], order: AwaitAnswer) -> None:
    await anyio.sleep(order.after)
    await emit.send(AnswerLasted(ticket=order.ticket))


async def _leave(mouth: Mouth, order: Leave) -> None:
    await anyio.sleep(max(0.0, order.until - mouth.clock()))
    logger.info("leaving: the goodbye has been said")
    await mouth.assistant.close()


async def _play_music(hold_music: HoldMusic, shell: _Shell, *, task_status: TaskStatus[None]) -> None:
    with anyio.CancelScope() as scope:
        shell.scopes.append(scope)
        task_status.started()
        await hold_music()


async def _start_music(mouth: Mouth, shell: _Shell, tasks: TaskGroup) -> None:
    if mouth.hold_music is not None:
        await tasks.start(_play_music, mouth.hold_music, shell)


def _stop_music(mouth: Mouth, shell: _Shell) -> None:
    if mouth.hold_music is None or not shell.scopes:
        return
    for scope in shell.scopes:
        scope.cancel()
    shell.scopes.clear()
    mouth.speaker.stop()
    mouth.hold_music.fade()
    logger.info("hold music stopped")


async def _later(
    mouth: Mouth, emit: ObjectSendStream[Event], command: AwaitSilence | AwaitHold | AwaitAnswer | Leave
) -> None:
    match command:
        case AwaitSilence():
            await _await_silence(mouth, emit, command)
        case AwaitHold():
            await _await_hold(emit, command)
        case AwaitAnswer():
            await _await_answer(emit, command)
        case Leave():
            await _leave(mouth, command)
        case _:
            assert_never(command)


def _voice(
    mouth: Mouth,
    emit: ObjectSendStream[Event],
    tasks: TaskGroup,
    shell: _Shell,
    command: Synthesize | CancelSynthesis | Play | StopPlaying,
) -> None:
    match command:
        case Synthesize():
            _start_synthesis(mouth, emit, tasks, shell, command)
        case CancelSynthesis():
            _cancel_synthesis(shell, command)
        case Play(pcm=pcm):
            mouth.speaker.play(pcm)
        case StopPlaying(heard_at=heard_at):
            mouth.speaker.stop()
            logger.info(
                "interrupted, playback stopped %.0f ms after the voice was heard", (mouth.clock() - heard_at) * 1000
            )
        case _:
            assert_never(command)


async def _execute(
    mouth: Mouth, emit: ObjectSendStream[Event], tasks: TaskGroup, shell: _Shell, command: Command
) -> None:
    match command:
        case Synthesize() | CancelSynthesis() | Play() | StopPlaying():
            _voice(mouth, emit, tasks, shell, command)
        case AwaitSilence() | AwaitHold() | AwaitAnswer() | Leave():
            _ = tasks.start_soon(_later, mouth, emit, command)
        case Acknowledge():
            _acknowledge(mouth, shell, command)
        case Announce():
            _announce(mouth, command)
        case StartHoldMusic():
            await _start_music(mouth, shell, tasks)
        case StopHoldMusic():
            _stop_music(mouth, shell)
        case Forward():
            await _forward(mouth, shell, command)
        case _:
            assert_never(command)


def _report(mouth: Mouth, reports: tuple[Report, ...]) -> None:
    for report in reports:
        mouth.telemetry(report)


def _observe(mouth: Mouth, shell: _Shell, item: Event | Command) -> None:
    shell.trace, reports = observe(shell.trace, mouth.clock(), item)
    _report(mouth, reports)


async def hold_conversation(mouth: Mouth, events: AsyncIterable[Event], emit: ObjectSendStream[Event]) -> None:
    state = Conversation(
        settle=mouth.settle,
        hold_music_delay=mouth.hold_music_delay,
        unanswered=mouth.unanswered,
        unanswered_after=mouth.unanswered_after,
    )
    shell = _Shell()
    try:
        async with anyio.create_task_group() as tasks:
            async for event in events:
                _observe(mouth, shell, event)
                state, commands = step(state, event)
                for command in commands:
                    _observe(mouth, shell, command)
                    await _execute(mouth, emit, tasks, shell, command)
            tasks.cancel_scope.cancel()
    finally:
        _report(mouth, close(shell.trace))
