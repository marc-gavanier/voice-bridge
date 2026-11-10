import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

import anyio
from pymumble_rev import events, opus

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping

    from anyio.abc import ObjectReceiveStream, ObjectSendStream
    from pymumble_rev import ServerState, User
    from pymumble_rev.audio import PcmBuffer


logger = logging.getLogger(__name__)

STALL_THRESHOLD: Final = 0.1
FRAME_DURATION: Final = 0.01
MUMBLE_RATE: Final = 48000


@dataclass(frozen=True, slots=True, kw_only=True)
class Packet:
    pcm: bytes
    at: float
    frame_number: int
    last: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Stall:
    waited: float
    frames_skipped: int


def _frames_in(packet: Packet) -> int:
    return round(len(packet.pcm) / 2 / MUMBLE_RATE / FRAME_DURATION)


def stall(previous: Packet | None, packet: Packet) -> Stall | None:
    if previous is None or previous.last or packet.at - previous.at <= STALL_THRESHOLD:
        return None
    skipped = packet.frame_number - previous.frame_number - _frames_in(previous)
    return Stall(waited=round(packet.at - previous.at, 6), frames_skipped=max(0, skipped))


class Session(Protocol):
    @property
    def state(self) -> ServerState: ...
    def events(self) -> AsyncIterator[events.Event]: ...


type Listened = Callable[[User], bool]


def holds_certificate(certificate_hash: str) -> Listened:
    return lambda user: user.cert_hash == certificate_hash


def named(name: str) -> Listened:
    return lambda user: user.name == name


def is_listened(users: Mapping[int, User], session: int, listened: Listened) -> bool:
    user = users.get(session)
    return user is not None and listened(user)


async def pump_audio(
    session: Session, listened: Listened, packets: ObjectSendStream[Packet], clock: Callable[[], float]
) -> None:
    decoder = opus.Decoder(channels=1)
    previous: Packet | None = None
    async for event in session.events():
        if isinstance(event, events.AudioReceived) and is_listened(session.state.users, event.sender_session, listened):
            packet = Packet(
                pcm=decoder.decode(event.opus_data),
                at=clock(),
                frame_number=event.frame_number,
                last=event.is_terminator,
            )
            stalled = stall(previous, packet)
            if stalled:
                logger.info(
                    "audio stalled %.0f ms before frame %d, %d frames skipped",
                    stalled.waited * 1000,
                    packet.frame_number,
                    stalled.frames_skipped,
                )
            await packets.send(packet)
            decoder = opus.Decoder(channels=1) if event.is_terminator else decoder
            previous = packet


async def _receive_or_none(packets: ObjectReceiveStream[Packet], patience: float) -> Packet | None:
    with anyio.move_on_after(patience):
        return await packets.receive()
    return None


async def with_pauses(packets: ObjectReceiveStream[Packet], patience: float) -> AsyncGenerator[Packet | None]:
    try:
        while True:
            yield await _receive_or_none(packets, patience)
    except anyio.EndOfStream:
        return


@dataclass(frozen=True, slots=True, kw_only=True)
class Loudspeaker:
    buffer: PcmBuffer

    def play(self, pcm: bytes) -> None:
        if self.buffer.buffered == 0:
            logger.info("playback starts, first packet within one 20 ms frame")
        _ = self.buffer.write(pcm, timeout=0)

    def stop(self) -> None:
        self.buffer.clear()
