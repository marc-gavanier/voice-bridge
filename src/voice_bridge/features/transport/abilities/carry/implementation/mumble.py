import logging
from dataclasses import dataclass
from itertools import count
from typing import TYPE_CHECKING, Final, Protocol

from pymumble_rev import events, opus

from voice_bridge.features.transport.abilities.carry.domain.received import (
    Disconnected,
    Frame,
    Reconnected,
    SpeakerJoined,
    SpeakerLeft,
    Stalled,
)
from voice_bridge.libraries.audio.pcm import duration

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

    from pymumble_rev import ServerState, User

    from voice_bridge.features.transport.abilities.carry.domain.ports import Outgoing
    from voice_bridge.features.transport.abilities.carry.domain.received import Received


logger = logging.getLogger(__name__)

STALL_THRESHOLD: Final = 0.1
RECOVERY_WINDOW: Final = 0.2
FRAME_DURATION: Final = 0.01
MUMBLE_RATE: Final = opus.SAMPLE_RATE


@dataclass(frozen=True, slots=True, kw_only=True)
class Stall:
    waited: float
    frames_skipped: int


def _frames_in(frame: Frame) -> int:
    return round(duration(frame.pcm, MUMBLE_RATE) / FRAME_DURATION)


def stall(previous: Frame | None, frame: Frame) -> Stall | None:
    if previous is None or previous.last or frame.at - previous.at <= STALL_THRESHOLD:
        return None
    skipped = frame.frame_number - previous.frame_number - _frames_in(previous)
    return Stall(waited=round(frame.at - previous.at, 6), frames_skipped=max(0, skipped))


@dataclass(frozen=True, slots=True, kw_only=True)
class Recovery:
    since: float
    audio: float

    @classmethod
    def after(cls, frame: Frame) -> Recovery:
        return cls(since=frame.at, audio=duration(frame.pcm, MUMBLE_RATE))

    @property
    def pace(self) -> float:
        return self.audio / RECOVERY_WINDOW


def recovered(recovery: Recovery, frame: Frame) -> Recovery | None:
    if frame.at - recovery.since >= RECOVERY_WINDOW:
        return None
    return Recovery(since=recovery.since, audio=round(recovery.audio + duration(frame.pcm, MUMBLE_RATE), 6))


def _log_recovery(recovery: Recovery | None) -> None:
    if recovery is not None:
        logger.info(
            "after the stall, %.2f s of audio arrived within %.0f ms (%.1fx real time)",
            recovery.audio,
            RECOVERY_WINDOW * 1000,
            recovery.pace,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Sent:
    outgoing: Outgoing

    def read(self, size: int) -> bytes:
        return self.outgoing(size)


class Client(Protocol):
    @property
    def state(self) -> ServerState: ...
    @property
    def close_reason(self) -> str | None: ...
    def events(self) -> AsyncIterator[events.Event]: ...
    def play(self, source: Sent, /) -> object: ...


type Listened = Callable[[User], bool]
type Connection = Callable[[Callable[[Client], Awaitable[None]]], Awaitable[None]]


def holds_certificate(certificate_hash: str) -> Listened:
    return lambda user: user.cert_hash == certificate_hash


def named(name: str) -> Listened:
    return lambda user: user.name == name


def is_listened(users: Mapping[int, User], session: int, listened: Listened) -> bool:
    user = users.get(session)
    return user is not None and listened(user)


def _report_ignored(users: Mapping[int, User], event: events.AudioReceived) -> None:
    user = users.get(event.sender_session)
    if event.is_terminator and user is not None:
        logger.info("ignored a transmission from %r, certificate hash %s", user.name, user.cert_hash)


def _who(user: User, listened: Listened) -> str:
    return f"session {user.session}, the speaker" if listened(user) else f"session {user.session}"


def _removal(event: events.UserLeft) -> str:
    if event.actor is None:
        return ""
    how = "banned" if event.ban else "kicked"
    return f", {how} by session {event.actor}: {event.reason!r}"


def _report_presence(event: events.Event, listened: Listened) -> None:
    match event:
        case events.UserJoined(user=user):
            logger.info("%r joined, %s", user.name, _who(user, listened))
        case events.UserLeft(user=user):
            logger.info("%r left, %s%s", user.name, _who(user, listened), _removal(event))
        case events.UserUpdated(user=user, changed=changed) if "channel_id" in changed:
            logger.info("%r moved to channel %d, %s", user.name, user.channel_id, _who(user, listened))
        case _:
            pass


def _presence(event: events.Event, listened: Listened) -> Received | None:
    match event:
        case events.UserJoined(user=user) if listened(user):
            return SpeakerJoined()
        case events.UserLeft(user=user) if listened(user):
            return SpeakerLeft()
        case _:
            return None


async def pump(
    client: Client,
    listened: Listened,
    receive: Callable[[Received], Awaitable[None]],
    clock: Callable[[], float],
) -> None:
    decoder = opus.Decoder(channels=1)
    previous: Frame | None = None
    recovery: Recovery | None = None
    async for event in client.events():
        _report_presence(event, listened)
        presence = _presence(event, listened)
        if presence is not None:
            await receive(presence)
        if isinstance(event, events.AudioReceived) and not is_listened(
            client.state.users, event.sender_session, listened
        ):
            _report_ignored(client.state.users, event)
        if isinstance(event, events.AudioReceived) and is_listened(client.state.users, event.sender_session, listened):
            frame = Frame(
                pcm=decoder.decode(event.opus_data),
                at=clock(),
                frame_number=event.frame_number,
                last=event.is_terminator,
            )
            stalled = stall(previous, frame)
            following = None if recovery is None or stalled else recovered(recovery, frame)
            if following is None:
                _log_recovery(recovery)
            recovery = following
            if stalled:
                logger.info(
                    "audio stalled %.0f ms before frame %d, %d frames skipped",
                    stalled.waited * 1000,
                    frame.frame_number,
                    stalled.frames_skipped,
                )
                await receive(Stalled(waited=stalled.waited))
                recovery = Recovery.after(frame)
            await receive(frame)
            decoder = opus.Decoder(channels=1) if event.is_terminator else decoder
            previous = frame


@dataclass(frozen=True, slots=True, kw_only=True)
class Mumble:
    connection: Connection
    listened: Listened
    clock: Callable[[], float]

    @property
    def rate(self) -> int:
        return MUMBLE_RATE

    async def carry(self, receive: Callable[[Received], Awaitable[None]], outgoing: Outgoing, /) -> None:
        connections = count()

        async def session(client: Client) -> None:
            if next(connections):
                await receive(Reconnected())
            _ = client.play(Sent(outgoing=outgoing))
            await pump(client, self.listened, receive, self.clock)
            await receive(Disconnected(reason=client.close_reason))

        await self.connection(session)
