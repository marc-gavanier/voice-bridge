from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

import anyio
import pytest

from voice_bridge.features.transport.abilities.carry.domain.ports import Outgoing, Transport
from voice_bridge.features.transport.abilities.carry.domain.received import (
    Disconnected,
    Frame,
    Received,
    Reconnected,
    SpeakerJoined,
    SpeakerLeft,
    Stalled,
)
from voice_bridge.features.transport.abilities.carry.implementation.carry import carry, with_pauses

pytestmark = pytest.mark.anyio

TWENTY_MS = bytes(1920)
FRAME = Frame(pcm=TWENTY_MS, at=1.0, frame_number=0, last=False)
FRAMES_ALREADY_WAITING_PATIENCE: Final = 30.0
NO_FRAME_PATIENCE: Final = 0.01


@dataclass(frozen=True, slots=True, kw_only=True)
class FakeTransport:
    received: tuple[Received, ...]
    rate: int = 48000
    sent: list[bytes] = field(default_factory=list[bytes])

    async def carry(self, receive: Callable[[Received], Awaitable[None]], outgoing: Outgoing, /) -> None:
        self.sent.append(outgoing(len(TWENTY_MS)))
        for each in self.received:
            await receive(each)


def outgoing_audio(size: int, /) -> bytes:
    return b"\x01" * size


@dataclass(frozen=True, slots=True)
class Delivered:
    frames: list[Frame] = field(default_factory=list[Frame])
    stalls: list[float] = field(default_factory=list[float])

    async def frame(self, frame: Frame) -> None:
        self.frames.append(frame)


async def delivered(*received: Received) -> Delivered:
    delivery = Delivered()
    transport: Transport = FakeTransport(received=received)
    await carry(transport, outgoing_audio, delivery.frame, delivery.stalls.append)
    return delivery


async def test_the_transport_sends_what_the_outgoing_audio_gives() -> None:
    transport = FakeTransport(received=())
    await carry(transport, outgoing_audio, Delivered().frame, Delivered().stalls.append)
    assert transport.sent == [outgoing_audio(len(TWENTY_MS))]


async def test_the_speakers_frames_are_passed_on() -> None:
    assert (await delivered(FRAME)).frames == [FRAME]


async def test_a_stall_is_passed_on_with_its_wait() -> None:
    assert (await delivered(Stalled(waited=0.5))).stalls == [0.5]


async def test_a_stall_is_not_a_frame() -> None:
    assert (await delivered(Stalled(waited=0.5))).frames == []


async def test_the_speaker_coming_and_going_passes_nothing_on() -> None:
    assert await delivered(SpeakerJoined(), SpeakerLeft()) == Delivered()


async def test_a_disconnection_is_logged_with_its_reason(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await delivered(Disconnected(reason="server shut down"))
    assert "disconnected from the transport ('server shut down'), reconnecting" in caplog.text


async def test_a_reconnection_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await delivered(Reconnected())
    assert "reconnected to the transport" in caplog.text


async def paced(*frames: Frame, patience: float) -> list[Frame | None]:
    sent, received = anyio.create_memory_object_stream[Frame](10)
    async with received:
        async with sent:
            for frame in frames:
                sent.send_nowait(frame)
        return [tick async for tick in with_pauses(received, patience)]


async def test_frames_come_through_as_they_arrive() -> None:
    assert await paced(FRAME, patience=FRAMES_ALREADY_WAITING_PATIENCE) == [FRAME]


async def test_a_pause_comes_through_when_no_frame_arrives_in_time() -> None:
    sent, received = anyio.create_memory_object_stream[Frame](10)
    async with sent, received:
        ticks = with_pauses(received, NO_FRAME_PATIENCE)
        tick = await anext(ticks)
        await ticks.aclose()
    assert tick is None
