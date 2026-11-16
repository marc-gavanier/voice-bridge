from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

import pytest
from pymumble_rev import ServerState, User, events, opus
from pymumble_rev.audio import AudioSource

from voice_bridge.features.transport.abilities.carry.domain.received import (
    Disconnected,
    Frame,
    Received,
    Reconnected,
    SpeakerJoined,
    SpeakerLeft,
    Stalled,
)
from voice_bridge.features.transport.abilities.carry.implementation.mumble import (
    MUMBLE_RATE,
    Client,
    Mumble,
    Recovery,
    Stall,
    holds_certificate,
    is_listened,
    named,
    pump,
    recovered,
    stall,
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


@dataclass
class FakeClient:
    received: tuple[events.Event, ...] = ()
    state: ServerState = field(default_factory=lambda: ServerState(session=3, users=USERS))
    close_reason: str | None = "server shut down"
    playing: list[AudioSource] = field(default_factory=list[AudioSource])

    async def events(self) -> AsyncIterator[events.Event]:
        for event in self.received:
            yield event

    def play(self, source: AudioSource, /) -> None:
        self.playing.append(source)


async def pumped(*received: events.Event, clock: Callable[[], float] = lambda: 42.0) -> list[Received]:
    carried: list[Received] = []

    async def receive(each: Received) -> None:
        carried.append(each)

    await pump(FakeClient(received=received), holds_certificate(SPEAKER_HASH), receive, clock)
    return carried


async def frames_of(*received: events.Event, clock: Callable[[], float] = lambda: 42.0) -> list[Frame]:
    return [each for each in await pumped(*received, clock=clock) if isinstance(each, Frame)]


async def stalls_of(*received: events.Event, arrivals: tuple[float, ...]) -> list[Received]:
    return [each for each in await pumped(*received, clock=iter(arrivals).__next__) if isinstance(each, Stalled)]


async def test_the_speaker_audio_is_decoded_to_twenty_milliseconds_of_pcm() -> None:
    assert len((await frames_of(audio_from(1, 0)))[0].pcm) == len(TWENTY_MS)


async def test_a_frame_keeps_its_frame_number() -> None:
    assert (await frames_of(audio_from(1, 7)))[0].frame_number == 7


async def test_a_frame_is_stamped_with_the_time_it_arrived() -> None:
    assert (await frames_of(audio_from(1, 0)))[0].at == 42.0


async def test_a_stall_is_carried_with_its_wait() -> None:
    assert await stalls_of(audio_from(1, 0), audio_from(1, 2), arrivals=(1.0, 1.5)) == [Stalled(waited=0.5)]


async def test_frames_on_time_carry_no_stall() -> None:
    assert await stalls_of(audio_from(1, 0), audio_from(1, 1), arrivals=(1.0, 1.02)) == []


async def test_the_stall_comes_before_the_frame_that_ended_it() -> None:
    arrivals = iter([1.0, 1.5])
    assert [type(each) for each in await pumped(audio_from(1, 0), audio_from(1, 2), clock=lambda: next(arrivals))] == [
        Frame,
        Stalled,
        Frame,
    ]


async def test_the_audio_of_other_users_is_ignored() -> None:
    assert await pumped(audio_from(2, 0), audio_from(3, 0)) == []


async def test_the_speaker_can_talk_again_after_a_pause() -> None:
    assert len(await frames_of(audio_from(1, 0, last=True), audio_from(1, 1))) == 2


def arrived(at: float, frame_number: int, *, last: bool = False) -> Frame:
    return Frame(pcm=TWENTY_MS, at=at, frame_number=frame_number, last=last)


def test_the_first_frame_is_never_a_stall() -> None:
    assert stall(None, arrived(1.0, 0)) is None


def test_frames_arriving_every_twenty_milliseconds_are_not_a_stall() -> None:
    assert stall(arrived(1.0, 0), arrived(1.02, 2)) is None


def test_a_long_wait_in_the_middle_of_speech_is_a_stall() -> None:
    assert stall(arrived(1.0, 0), arrived(1.5, 2)) == Stall(waited=0.5, frames_skipped=0)


def test_a_stall_tells_the_frames_skipped() -> None:
    assert stall(arrived(1.0, 0), arrived(1.5, 8)) == Stall(waited=0.5, frames_skipped=6)


def test_the_pause_after_the_end_of_a_transmission_is_not_a_stall() -> None:
    assert stall(arrived(1.0, 0, last=True), arrived(5.0, 2)) is None


async def test_a_frame_remembers_it_ended_a_transmission() -> None:
    assert (await frames_of(audio_from(1, 0, last=True)))[0].last


async def test_a_frame_in_the_middle_of_a_transmission_does_not_end_it() -> None:
    assert not (await frames_of(audio_from(1, 0)))[0].last


async def test_a_stalled_frame_still_comes_through() -> None:
    arrivals = iter([1.0, 1.5])
    assert len(await frames_of(audio_from(1, 0), audio_from(1, 2), clock=lambda: next(arrivals))) == 2


async def test_the_end_of_an_ignored_transmission_is_not_passed_on() -> None:
    assert await pumped(audio_from(2, 0, last=True), audio_from(9, 0, last=True)) == []


def test_the_recovery_starts_with_the_audio_of_the_frame_after_the_stall() -> None:
    assert Recovery.after(arrived(1.5, 2)) == Recovery(since=1.5, audio=0.02)


def test_a_frame_within_the_window_adds_its_audio_to_the_recovery() -> None:
    assert recovered(Recovery(since=1.5, audio=0.02), arrived(1.52, 4)) == Recovery(since=1.5, audio=0.04)


def test_a_frame_after_the_window_ends_the_recovery() -> None:
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


async def test_a_stall_is_logged_with_the_frames_skipped(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    arrivals = iter([1.0, 1.5])
    _ = await pumped(audio_from(1, 0), audio_from(1, 8), clock=lambda: next(arrivals))
    assert "audio stalled 500 ms before frame 8, 6 frames skipped" in caplog.text


async def test_the_speaker_joining_is_carried() -> None:
    assert await pumped(events.UserJoined(user=USERS[1])) == [SpeakerJoined()]


async def test_another_user_joining_is_not_carried() -> None:
    assert await pumped(events.UserJoined(user=USERS[3])) == []


async def test_the_speaker_leaving_is_carried() -> None:
    assert await pumped(events.UserLeft(user=USERS[1], actor=None, reason="", ban=False)) == [SpeakerLeft()]


async def test_another_user_leaving_is_not_carried() -> None:
    assert await pumped(events.UserLeft(user=USERS[2], actor=None, reason="", ban=False)) == []


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


async def test_another_users_transmission_is_logged_with_their_certificate(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await pumped(audio_from(2, 0, last=True))
    assert "ignored a transmission from 'marc', certificate hash someone else" in caplog.text


def connections_to(*clients: FakeClient) -> Callable[[Callable[[Client], Awaitable[None]]], Awaitable[None]]:
    async def connection(session: Callable[[Client], Awaitable[None]]) -> None:
        for client in clients:
            await session(client)

    return connection


async def carried_by(mumble: Mumble) -> list[Received]:
    carried: list[Received] = []

    async def receive(each: Received) -> None:
        carried.append(each)

    await mumble.carry(receive, outgoing_audio)
    return carried


def outgoing_audio(size: int, /) -> bytes:
    return bytes(size // 2)


def mumble_over(*clients: FakeClient) -> Mumble:
    return Mumble(connection=connections_to(*clients), listened=holds_certificate(SPEAKER_HASH), clock=lambda: 42.0)


def test_mumble_carries_audio_at_its_opus_rate() -> None:
    assert mumble_over().rate == MUMBLE_RATE


def sent(clients: tuple[FakeClient, ...]) -> list[bytes | None]:
    return [source.read(len(TWENTY_MS)) for client in clients for source in client.playing]


async def test_each_connection_sends_the_outgoing_audio() -> None:
    clients = (FakeClient(), FakeClient())
    _ = await carried_by(mumble_over(*clients))
    assert sent(clients) == [bytes(len(TWENTY_MS) // 2)] * 2


async def test_the_speakers_audio_is_carried_from_the_connection() -> None:
    assert [type(each) for each in await carried_by(mumble_over(FakeClient(received=(audio_from(1, 0),))))] == [
        Frame,
        Disconnected,
    ]


async def test_the_end_of_a_connection_is_carried_with_its_reason() -> None:
    assert await carried_by(mumble_over(FakeClient())) == [Disconnected(reason="server shut down")]


async def test_a_connection_after_the_first_is_carried_as_a_reconnection() -> None:
    assert await carried_by(mumble_over(FakeClient(), FakeClient())) == [
        Disconnected(reason="server shut down"),
        Reconnected(),
        Disconnected(reason="server shut down"),
    ]
