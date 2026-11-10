from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import anyio
import pytest
from pymumble_rev import ServerState, User, events, opus
from pymumble_rev.audio import PcmBuffer

from voice_bridge.libraries.mumble.audio import (
    Loudspeaker,
    Packet,
    holds_certificate,
    is_listened,
    named,
    pump_audio,
    with_pauses,
)

pytestmark = pytest.mark.anyio

SPEAKER_HASH = "6f0b58787b96ff978ba512c74a1c3ca4aabab441"
USERS = {
    1: User(session=1, name="marc", cert_hash=SPEAKER_HASH),
    2: User(session=2, name="marc", cert_hash="someone else"),
    3: User(session=3, name="claude"),
}
TWENTY_MS = bytes(1920)


def test_the_user_holding_the_speaker_certificate_is_the_speaker() -> None:
    assert is_listened(USERS, 1, holds_certificate(SPEAKER_HASH))


def test_a_user_with_the_same_name_but_another_certificate_is_not_the_speaker() -> None:
    assert not is_listened(USERS, 2, holds_certificate(SPEAKER_HASH))


def test_a_user_without_certificate_is_not_the_speaker() -> None:
    assert not is_listened(USERS, 3, holds_certificate(SPEAKER_HASH))


def test_an_unknown_session_is_not_the_speaker() -> None:
    assert not is_listened(USERS, 9, holds_certificate(SPEAKER_HASH))


def test_a_user_can_be_listened_to_by_name_for_diagnostics() -> None:
    assert is_listened(USERS, 3, named("claude"))


def audio_from(session: int, frame_number: int, *, last: bool = False) -> events.AudioReceived:
    return events.AudioReceived(
        sender_session=session,
        frame_number=frame_number,
        opus_data=opus.Encoder(channels=1).encode(TWENTY_MS),
        context=0,
        is_terminator=last,
        volume_adjustment=1.0,
    )


@dataclass(frozen=True)
class FakeSession:
    received: tuple[events.Event, ...]
    state: ServerState = field(default_factory=lambda: ServerState(session=3, users=USERS))

    async def events(self) -> AsyncIterator[events.Event]:
        for event in self.received:
            yield event


async def pumped(*received: events.Event) -> list[Packet]:
    sent, packets = anyio.create_memory_object_stream[Packet](10)
    async with packets:
        async with sent:
            await pump_audio(FakeSession(received=received), holds_certificate(SPEAKER_HASH), sent, clock=lambda: 42.0)
        return [packet async for packet in packets]


async def test_the_speaker_audio_is_decoded_to_twenty_milliseconds_of_pcm() -> None:
    assert len((await pumped(audio_from(1, 0)))[0].pcm) == len(TWENTY_MS)


async def test_a_packet_keeps_its_frame_number() -> None:
    assert (await pumped(audio_from(1, 7)))[0].frame_number == 7


async def test_a_packet_is_stamped_with_the_time_it_arrived() -> None:
    assert (await pumped(audio_from(1, 0)))[0].at == 42.0


async def test_the_audio_of_other_users_is_ignored() -> None:
    assert await pumped(audio_from(2, 0), audio_from(3, 0)) == []


async def test_the_speaker_can_talk_again_after_a_pause() -> None:
    assert len(await pumped(audio_from(1, 0, last=True), audio_from(1, 1))) == 2


def test_playing_queues_the_audio() -> None:
    buffer = PcmBuffer(capacity=10.0)
    Loudspeaker(buffer=buffer).play(TWENTY_MS)
    assert buffer.buffered > 0


def test_playing_while_audio_is_queued_adds_to_it() -> None:
    buffer = PcmBuffer(capacity=10.0)
    speaker = Loudspeaker(buffer=buffer)
    speaker.play(TWENTY_MS)
    speaker.play(TWENTY_MS)
    assert buffer.buffered == pytest.approx(0.04)


def test_stopping_drops_the_queued_audio() -> None:
    buffer = PcmBuffer(capacity=10.0)
    speaker = Loudspeaker(buffer=buffer)
    speaker.play(TWENTY_MS)
    speaker.stop()
    assert buffer.buffered == 0


async def paced(*packets: Packet, patience: float = 0.01) -> list[Packet | None]:
    sent, received = anyio.create_memory_object_stream[Packet](10)
    async with received:
        async with sent:
            for packet in packets:
                sent.send_nowait(packet)
        return [tick async for tick in with_pauses(received, patience)]


async def test_packets_come_through_as_they_arrive() -> None:
    assert await paced(Packet(pcm=TWENTY_MS, at=1.0, frame_number=0)) == [Packet(pcm=TWENTY_MS, at=1.0, frame_number=0)]


async def test_a_pause_comes_through_when_no_packet_arrives_in_time() -> None:
    sent, received = anyio.create_memory_object_stream[Packet](10)
    async with sent, received:
        ticks = with_pauses(received, 0.01)
        tick = await anext(ticks)
        await ticks.aclose()
    assert tick is None
