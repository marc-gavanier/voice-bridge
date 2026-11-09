from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pymumble_rev import events, opus

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Mapping

    from anyio.abc import ObjectSendStream
    from pymumble_rev import ServerState, User
    from pymumble_rev.audio import PcmBuffer


@dataclass(frozen=True, slots=True, kw_only=True)
class Packet:
    pcm: bytes
    at: float
    frame_number: int


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
    async for event in session.events():
        if isinstance(event, events.AudioReceived) and is_listened(session.state.users, event.sender_session, listened):
            pcm = decoder.decode(event.opus_data)
            await packets.send(Packet(pcm=pcm, at=clock(), frame_number=event.frame_number))
            decoder = opus.Decoder(channels=1) if event.is_terminator else decoder


@dataclass(frozen=True, slots=True, kw_only=True)
class Loudspeaker:
    buffer: PcmBuffer

    def play(self, pcm: bytes) -> None:
        _ = self.buffer.write(pcm, timeout=0)

    def stop(self) -> None:
        self.buffer.clear()
