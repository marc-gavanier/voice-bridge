from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import anyio
import pytest
from pymumble_rev import ServerState, User, events, opus
from pymumble_rev.audio import PcmBuffer

from voice_bridge.libraries.mumble.audio import (
    Loudspeaker,
    Packet,
    Recovery,
    Stall,
    holds_certificate,
    is_listened,
    named,
    pump_audio,
    recovered,
    stall,
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


def no_stall(_seconds: float, /) -> None:
    return None


async def pumped(
    *received: events.Event, clock: Callable[[], float] = lambda: 42.0, stalled_for: Callable[[float], None] = no_stall
) -> list[Packet]:
    sent, packets = anyio.create_memory_object_stream[Packet](10)
    async with packets:
        async with sent:
            await pump_audio(
                FakeSession(received=received),
                holds_certificate(SPEAKER_HASH),
                sent,
                clock=clock,
                stalled_for=stalled_for,
            )
        return [packet async for packet in packets]


async def stalls_of(*received: events.Event, arrivals: tuple[float, ...]) -> list[float]:
    stalls: list[float] = []
    _ = await pumped(*received, clock=iter(arrivals).__next__, stalled_for=stalls.append)
    return stalls


async def test_the_speaker_audio_is_decoded_to_twenty_milliseconds_of_pcm() -> None:
    assert len((await pumped(audio_from(1, 0)))[0].pcm) == len(TWENTY_MS)


async def test_a_packet_keeps_its_frame_number() -> None:
    assert (await pumped(audio_from(1, 7)))[0].frame_number == 7


async def test_a_packet_is_stamped_with_the_time_it_arrived() -> None:
    assert (await pumped(audio_from(1, 0)))[0].at == 42.0


async def test_a_stall_is_reported_with_its_wait() -> None:
    assert await stalls_of(audio_from(1, 0), audio_from(1, 2), arrivals=(1.0, 1.5)) == [0.5]


async def test_packets_on_time_report_no_stall() -> None:
    assert await stalls_of(audio_from(1, 0), audio_from(1, 1), arrivals=(1.0, 1.02)) == []


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


def arrived(at: float, frame_number: int, *, last: bool = False) -> Packet:
    return Packet(pcm=TWENTY_MS, at=at, frame_number=frame_number, last=last)


def test_the_first_packet_is_never_a_stall() -> None:
    assert stall(None, arrived(1.0, 0)) is None


def test_packets_arriving_every_twenty_milliseconds_are_not_a_stall() -> None:
    assert stall(arrived(1.0, 0), arrived(1.02, 2)) is None


def test_a_long_wait_in_the_middle_of_speech_is_a_stall() -> None:
    assert stall(arrived(1.0, 0), arrived(1.5, 2)) == Stall(waited=0.5, frames_skipped=0)


def test_a_stall_tells_the_frames_skipped() -> None:
    assert stall(arrived(1.0, 0), arrived(1.5, 8)) == Stall(waited=0.5, frames_skipped=6)


def test_the_pause_after_the_end_of_a_transmission_is_not_a_stall() -> None:
    assert stall(arrived(1.0, 0, last=True), arrived(5.0, 2)) is None


async def test_a_packet_remembers_it_ended_a_transmission() -> None:
    assert (await pumped(audio_from(1, 0, last=True)))[0].last


async def test_a_stalled_packet_still_comes_through() -> None:
    arrivals = iter([1.0, 1.5])
    assert len(await pumped(audio_from(1, 0), audio_from(1, 2), clock=lambda: next(arrivals))) == 2


async def test_the_end_of_an_ignored_transmission_is_not_passed_on() -> None:
    assert await pumped(audio_from(2, 0, last=True), audio_from(9, 0, last=True)) == []


def test_the_recovery_starts_with_the_audio_of_the_packet_after_the_stall() -> None:
    assert Recovery.after(arrived(1.5, 2)) == Recovery(since=1.5, audio=0.02)


def test_a_packet_within_the_window_adds_its_audio_to_the_recovery() -> None:
    assert recovered(Recovery(since=1.5, audio=0.02), arrived(1.52, 4)) == Recovery(since=1.5, audio=0.04)


def test_a_packet_after_the_window_ends_the_recovery() -> None:
    assert recovered(Recovery(since=1.5, audio=0.02), arrived(1.8, 4)) is None


def test_audio_arriving_at_its_own_pace_recovers_at_real_time() -> None:
    assert Recovery(since=1.5, audio=0.2).pace == pytest.approx(1.0)


def test_held_back_audio_arriving_in_a_burst_recovers_faster_than_real_time() -> None:
    assert Recovery(since=1.5, audio=2.4).pace == pytest.approx(12.0)


async def test_the_audio_that_follows_a_stall_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    arrivals = iter([1.0, 1.5, 1.5, 1.9])
    _ = await pumped(
        audio_from(1, 0), audio_from(1, 2), audio_from(1, 4), audio_from(1, 6), clock=lambda: next(arrivals)
    )
    assert "after the stall, 0.04 s of audio arrived within 200 ms (0.2x real time)" in caplog.text


async def test_a_new_stall_logs_the_recovery_of_the_previous_one(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    arrivals = iter([1.0, 1.5, 1.65])
    _ = await pumped(audio_from(1, 0), audio_from(1, 2), audio_from(1, 4), clock=lambda: next(arrivals))
    assert "after the stall, 0.02 s of audio arrived within 200 ms (0.1x real time)" in caplog.text


async def test_a_user_joining_is_logged_with_their_session(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(events.UserJoined(user=USERS[3]))
    assert "'claude' joined, session 3" in caplog.text


async def test_the_speaker_joining_is_logged_as_the_speaker(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(events.UserJoined(user=USERS[1]))
    assert "'marc' joined, session 1, the speaker" in caplog.text


async def test_the_speaker_leaving_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(events.UserLeft(user=USERS[1], actor=None, reason="", ban=False))
    assert "'marc' left, session 1, the speaker" in caplog.text


async def test_a_user_removed_by_another_is_logged_with_who_and_why(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(events.UserLeft(user=USERS[2], actor=3, reason="spam", ban=True))
    assert "'marc' left, session 2, banned by session 3: 'spam'" in caplog.text


async def test_a_user_kicked_by_another_is_logged_as_kicked(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(events.UserLeft(user=USERS[2], actor=3, reason="", ban=False))
    assert "'marc' left, session 2, kicked by session 3: ''" in caplog.text


async def test_a_user_moving_to_another_channel_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    moved = User(session=1, name="marc", cert_hash=SPEAKER_HASH, channel_id=4)
    _ = await pumped(events.UserUpdated(user=moved, previous=USERS[1], changed=frozenset({"channel_id"}), actor=None))
    assert "'marc' moved to channel 4, session 1, the speaker" in caplog.text


async def test_other_user_changes_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    muted = User(session=1, name="marc", cert_hash=SPEAKER_HASH, self_mute=True)
    _ = await pumped(events.UserUpdated(user=muted, previous=USERS[1], changed=frozenset({"self_mute"}), actor=None))
    assert caplog.text == ""
