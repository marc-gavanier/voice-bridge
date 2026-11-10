from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import pytest

from voice_bridge.features.recording.abilities.record import Recorder, advance, record, save
from voice_bridge.features.recording.domain.take import Heard, Take, begin, extend
from voice_bridge.libraries.audio.wav import decode
from voice_bridge.libraries.mumble.audio import Packet

TWENTY_MS = b"\x01\x00" * 960
RECORDER = Recorder(directory=Path("unused"), rate=48000, silence=1.5)


def packet(at: float) -> Packet:
    return Packet(pcm=TWENTY_MS, at=at, frame_number=round(at * 100))


def heard(at: float) -> Heard:
    return Heard(pcm=TWENTY_MS, at=at, frame_number=round(at * 100), duration=0.02)


def take_started_at(at: float) -> Take:
    return begin(heard(at))


def test_a_first_packet_begins_a_take() -> None:
    assert advance(RECORDER, None, packet(1.0), now=1.0) == (take_started_at(1.0), None)


def test_a_pause_without_take_records_nothing() -> None:
    assert advance(RECORDER, None, None, now=1.0) == (None, None)


def test_a_packet_soon_after_extends_the_take() -> None:
    assert advance(RECORDER, take_started_at(1.0), packet(1.02), now=1.02) == (
        extend(take_started_at(1.0), heard(1.02)),
        None,
    )


def test_a_packet_after_a_long_silence_finishes_the_take_and_begins_another() -> None:
    assert advance(RECORDER, take_started_at(1.0), packet(5.0), now=5.0) == (take_started_at(5.0), take_started_at(1.0))


def test_a_long_pause_finishes_the_take() -> None:
    assert advance(RECORDER, take_started_at(1.0), None, now=5.0) == (None, take_started_at(1.0))


@pytest.mark.anyio
async def test_a_saved_take_is_a_wav_of_its_audio(tmp_path: Path) -> None:
    path = await save(Recorder(directory=tmp_path, rate=48000), take_started_at(1.0))
    assert decode(await anyio.Path(path).read_bytes(), rate=48000) == TWENTY_MS


async def two_takes() -> AsyncIterator[Packet | None]:
    yield packet(1.0)
    yield packet(5.0)
    yield None


@pytest.mark.anyio
async def test_recording_saves_each_finished_take(tmp_path: Path) -> None:
    times = iter([1.0, 5.0, 10.0])
    await record(Recorder(directory=tmp_path, rate=48000), two_takes(), clock=lambda: next(times))
    assert len([wav async for wav in anyio.Path(tmp_path).rglob("*.wav")]) == 2
