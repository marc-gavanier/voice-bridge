from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import pytest
from anyio import wait_all_tasks_blocked
from anyio.abc import ObjectReceiveStream
from anyio.streams.memory import MemoryObjectSendStream

from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Acknowledgement
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.hold_conversation import (
    Mouth,
    hold_conversation,
)
from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Event,
    SilenceLasted,
    SpeechEnded,
    Transcribed,
    VoiceDetected,
)

pytestmark = pytest.mark.anyio

SOUND = b"\x01\x00" * 4800
QUESTION_CLIP = b"\x02\x00" * 480
STATEMENT_CLIP = b"\x03\x00" * 480
MUSIC = b"\x04\x00" * 480
SOUND_DURATION = 0.1


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
    say: MemoryObjectSendStream[Event]
    played: ObjectReceiveStream[bytes]
    forwarded: ObjectReceiveStream[tuple[str, bool, str | None]]
    left: ObjectReceiveStream[float]


@asynccontextmanager
async def talking(
    acknowledgement: Acknowledgement = READY, *, music: bool = True, settle: float = 0.0
) -> AsyncGenerator[Talk]:
    say, events = anyio.create_memory_object_stream[Event](100)
    played_in, played_out = anyio.create_memory_object_stream[bytes](100)
    forwarded_in, forwarded_out = anyio.create_memory_object_stream[tuple[str, bool, str | None]](100)
    left_in, left_out = anyio.create_memory_object_stream[float](100)
    started = anyio.current_time()

    async def claude(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
        await forwarded_in.send((text, interrupted, acknowledgement))

    async def hold_music() -> None:
        played_in.send_nowait(MUSIC)

    async def leave() -> None:
        await left_in.send(anyio.current_time() - started)

    mouth = Mouth(
        voice=voiced,
        speaker=StreamedSpeaker(played_in),
        claude=claude,
        rate=48000,
        clock=lambda: 0.0,
        acknowledgement=acknowledgement,
        settle=settle,
        hold_music=hold_music if music else None,
        hold_music_delay=0.0,
        leave=leave,
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
        left_in,
        left_out,
        anyio.create_task_group() as tasks,
    ):
        _ = tasks.start_soon(hold_conversation, mouth, events, emit)
        yield Talk(say=say, played=played_out, forwarded=forwarded_out, left=left_out)
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


async def test_words_said_in_pieces_reach_claude_as_one_message() -> None:
    async with talking() as talk:
        talk.say.send_nowait(Transcribed(text="Je voudrais..."))
        talk.say.send_nowait(Transcribed(text="un ticket."))
        forwarded = await talk.forwarded.receive()
    assert forwarded == ("Je voudrais... un ticket.", False, "D'accord.")


async def test_words_joined_from_pieces_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking() as talk:
        talk.say.send_nowait(Transcribed(text="Je voudrais..."))
        talk.say.send_nowait(Transcribed(text="un ticket."))
        _ = await talk.forwarded.receive()
    assert "joined 2 pieces said with pauses" in caplog.text


async def test_an_interruption_stops_the_speaker() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        _ = await talk.played.receive()
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


async def test_an_announced_work_plays_the_hold_music_after_its_voice() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",), working=True))
        played = [await talk.played.receive(), await talk.played.receive()]
    assert played == [SOUND, MUSIC]


async def test_the_reply_stops_the_hold_music_before_it_plays() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",), working=True))
        _ = [await talk.played.receive(), await talk.played.receive()]
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = [await talk.played.receive(), await talk.played.receive()]
    assert played == [b"", SOUND]


async def test_without_hold_music_an_announced_work_stays_silent() -> None:
    async with talking(music=False) as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",), working=True))
        _ = await talk.played.receive()
        await anyio.sleep(SOUND_DURATION)
        await wait_all_tasks_blocked()
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_goodbye_leaves_once_its_voice_has_played() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("À demain.",), ending=True))
        played = await talk.played.receive()
        waited = await talk.left.receive()
    assert (played, waited >= SOUND_DURATION) == (SOUND, True)


async def test_the_silence_already_kept_since_the_end_of_the_voice_is_not_waited_again() -> None:
    async with talking(settle=60.0) as talk:
        await talk.say.send(SpeechEnded(at=-60.0))
        await talk.say.send(Transcribed(text="Bonjour."))
        with anyio.fail_after(1):
            forwarded = await talk.forwarded.receive()
    assert forwarded[0] == "Bonjour."
