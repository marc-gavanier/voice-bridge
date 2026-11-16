import logging
from typing import TYPE_CHECKING, assert_never

import anyio

from voice_bridge.features.transport.abilities.carry.domain.received import (
    Disconnected,
    Frame,
    Received,
    Reconnected,
    SpeakerJoined,
    SpeakerLeft,
    Stalled,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from anyio.abc import ObjectReceiveStream

    from voice_bridge.features.transport.abilities.carry.domain.ports import Outgoing, Transport

logger = logging.getLogger(__name__)


async def carry(
    transport: Transport,
    outgoing: Outgoing,
    frames: Callable[[Frame], Awaitable[None]],
    stalled: Callable[[float], None],
) -> None:
    async def receive(each: Received) -> None:
        match each:
            case Frame():
                await frames(each)
            case Stalled(waited=waited):
                stalled(waited)
            case Disconnected(reason=reason):
                logger.info("disconnected from the transport (%r), reconnecting", reason)
            case Reconnected():
                logger.info("reconnected to the transport")
            case SpeakerJoined() | SpeakerLeft():
                pass
            case _:
                assert_never(each)

    await transport.carry(receive, outgoing)


async def _receive_or_none(frames: ObjectReceiveStream[Frame], patience: float) -> Frame | None:
    with anyio.move_on_after(patience):
        return await frames.receive()
    return None


async def with_pauses(frames: ObjectReceiveStream[Frame], patience: float) -> AsyncGenerator[Frame | None]:
    try:
        while True:
            yield await _receive_or_none(frames, patience)
    except anyio.EndOfStream:
        return
