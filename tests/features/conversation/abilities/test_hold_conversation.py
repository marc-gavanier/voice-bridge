from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import pytest
from anyio import wait_all_tasks_blocked
from anyio.abc import ObjectReceiveStream, ObjectSendStream
from anyio.streams.memory import MemoryObjectSendStream

from voice_bridge.features.conversation.abilities.hold_conversation import Mouth, hold_conversation
from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Event,
    SilenceLasted,
    Transcribed,
    VoiceDetected,
)

pytestmark = pytest.mark.anyio

SOUND = b"\x01\x00" * 4800
QUESTION_CLIP = b"\x02\x00" * 480
STATEMENT_CLIP = b"\x03\x00" * 480
MUSIC = b"\x04\x00" * 480


@dataclass(frozen=True)
class StreamedSpeaker:
    played: MemoryObjectSendStream[bytes]

    def play(self, pcm: bytes) -> None:
        self.played.send_nowait(pcm)

    def stop(self) -> None:
        self.played.send_nowait(b"")


@dataclass(frozen=True)
class Clips:
    question: tuple[str, bytes] | None
    statement: tuple[str, bytes] | None

    def __call__(self, words: str) -> tuple[str, bytes] | None:
        return self.question if words.endswith("?") else self.statement


READY = Clips(question=("Voyons.", QUESTION_CLIP), statement=("D'accord.", STATEMENT_CLIP))
NOT_READY = Clips(question=None, statement=None)


async def voiced(sentence: str) -> bytes | None:
    return None if sentence.startswith("Silent") else SOUND


@dataclass(frozen=True)
class Talk:
    say: ObjectSendStream[Event]
    played: ObjectReceiveStream[bytes]
    forwarded: ObjectReceiveStream[tuple[str, bool, str | None]]


@asynccontextmanager
async def talking(acknowledgement: Clips = READY, *, music: bool = True) -> AsyncGenerator[Talk]:
    say, events = anyio.create_memory_object_stream[Event](100)
    played_in, played_out = anyio.create_memory_object_stream[bytes](100)
    forwarded_in, forwarded_out = anyio.create_memory_object_stream[tuple[str, bool, str | None]](100)

    async def claude(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
        await forwarded_in.send((text, interrupted, acknowledgement))

    async def hold_music() -> None:
        played_in.send_nowait(MUSIC)

    mouth = Mouth(
        voice=voiced,
        speaker=StreamedSpeaker(played_in),
        claude=claude,
        rate=48000,
        clock=lambda: 0.0,
        acknowledgement=acknowledgement,
        acknowledgement_delay=0.0,
        hold_music=hold_music if music else None,
        hold_music_delay=0.0,
    )
    emit = say.clone()
    async with (
        say,
        emit,
        events,
        played_in,
        played_out,
        forwarded_in,
        forwarded_out,
        anyio.create_task_group() as tasks,
    ):
        _ = tasks.start_soon(hold_conversation, mouth, events, emit)
        yield Talk(say=say, played=played_out, forwarded=forwarded_out)
        tasks.cancel_scope.cancel()


async def test_an_asked_sentence_is_played() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_sentence_without_voice_is_skipped_for_the_next_one() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Silent sentence.", "Spoken sentence.")))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_transcript_is_forwarded_to_claude() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Tu en es où ?"))
        forwarded = await talk.forwarded.receive()
    assert forwarded == ("Tu en es où ?", False, "Voyons.")


async def test_claude_learns_the_acknowledgement_that_is_played_after_its_words() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        _, _, announced = await talk.forwarded.receive()
        played = await talk.played.receive()
    assert (announced, played) == ("D'accord.", STATEMENT_CLIP)


async def test_claude_learns_nothing_when_no_clip_is_ready() -> None:
    async with talking(NOT_READY) as talk:
        await talk.say.send(Transcribed(text="Tu en es où ?"))
        forwarded = await talk.forwarded.receive()
    assert forwarded == ("Tu en es où ?", False, None)


async def test_claude_learns_nothing_for_words_that_will_not_be_acknowledged() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        _ = await talk.forwarded.receive()
        _ = await talk.played.receive()
        await talk.say.send(Transcribed(text="Et les logs."))
        forwarded = await talk.forwarded.receive()
    assert forwarded == ("Et les logs.", False, None)


async def test_an_interruption_stops_the_speaker() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        await talk.say.send(VoiceDetected(at=0.0))
        played = await talk.played.receive()
    assert played == b""


async def test_a_question_is_acknowledged_with_a_question_clip() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Tu en es où ?"))
        played = await talk.played.receive()
    assert played == QUESTION_CLIP


async def test_a_statement_is_acknowledged_with_a_statement_clip() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        played = await talk.played.receive()
    assert played == STATEMENT_CLIP


async def test_nothing_is_played_before_the_clips_are_ready() -> None:
    async with talking(NOT_READY) as talk:
        await talk.say.send(Transcribed(text="Tu en es où ?"))
        await talk.say.send(SilenceLasted(ticket=0, at=0.0))
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_long_wait_plays_the_hold_music() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        played = [await talk.played.receive(), await talk.played.receive()]
    assert played == [STATEMENT_CLIP, MUSIC]


async def test_the_reply_stops_the_hold_music_before_it_plays() -> None:
    async with talking() as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        _ = [await talk.played.receive(), await talk.played.receive()]
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = [await talk.played.receive(), await talk.played.receive()]
    assert played == [b"", SOUND]


async def test_without_hold_music_a_long_wait_stays_silent() -> None:
    async with talking(music=False) as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        _ = await talk.played.receive()
        await wait_all_tasks_blocked()
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND
