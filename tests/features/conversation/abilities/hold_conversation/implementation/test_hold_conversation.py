from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import pytest
from anyio import wait_all_tasks_blocked
from anyio.abc import ObjectReceiveStream
from anyio.streams.memory import MemoryObjectSendStream

from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import (
    Acknowledgement,
    Voice,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.hold_conversation import (
    Mouth,
    hold_conversation,
)
from voice_bridge.features.conversation.domain.turn_taking import (
    AgentsChanged,
    Asked,
    ClaudeBusy,
    Event,
    Recording,
    SilenceLasted,
    SoundDismissed,
    SpeechEnded,
    Transcribed,
    VoiceDetected,
)
from voice_bridge.features.conversation.domain.turn_trace import (
    Acknowledged,
    Counted,
    FinishedTurn,
    Forwarded,
    Report,
    Span,
    Understood,
)

pytestmark = pytest.mark.anyio

SOUND = b"\x01\x00" * 4800
QUESTION_CLIP = b"\x02\x00" * 480
STATEMENT_CLIP = b"\x03\x00" * 480
MUSIC = b"\x04\x00" * 480
FADE = b"\x05\x00" * 48
ANNOUNCEMENT_CLIP = b"\x06\x00" * 480
RECORDED = b"\x07\x00" * 4800
SOUND_DURATION = 0.1


@dataclass(frozen=True)
class StreamedSpeaker:
    played: MemoryObjectSendStream[bytes]

    def play(self, pcm: bytes) -> None:
        self.played.send_nowait(pcm)

    def stop(self) -> None:
        self.played.send_nowait(b"")


@dataclass(frozen=True)
class FakeMusic:
    played: MemoryObjectSendStream[bytes]

    async def __call__(self) -> None:
        self.played.send_nowait(MUSIC)

    def fade(self) -> None:
        self.played.send_nowait(FADE)


@dataclass(frozen=True)
class Clips:
    question: tuple[str, bytes] | None
    statement: tuple[str, bytes] | None

    def __call__(self, words: str) -> tuple[str, bytes] | None:
        return self.question if words.endswith("?") else self.statement


READY = Clips(question=("Voyons.", QUESTION_CLIP), statement=("D'accord.", STATEMENT_CLIP))
NOT_READY = Clips(question=None, statement=None)


QUESTION = Understood(route="question", ranking=(("question", 0.8), ("idea", 0.3)))
NOTHING = Understood(route=None, ranking=(("idea", 0.2),))


def understood(words: str) -> Understood:
    return QUESTION if words.endswith("?") else NOTHING


ANNOUNCED_SENTENCES = {2: "Two at work."}


def announced(at_work: int) -> tuple[str, bytes] | None:
    sentence = ANNOUNCED_SENTENCES.get(at_work)
    return None if sentence is None else (sentence, ANNOUNCEMENT_CLIP)


type Hear = Callable[[bytes], Awaitable[None]]


async def voiced(sentence: str, hear: Hear) -> bool:
    if sentence.startswith("Silent"):
        return False
    await hear(SOUND)
    return True


async def voiced_in_pieces(sentence: str, hear: Hear) -> bool:
    await hear(SOUND)
    await hear(sentence.encode())
    return True


async def broken_after_a_piece(sentence: str, hear: Hear) -> bool:
    await hear(SOUND)
    return not sentence.startswith("Broken")


async def hanging_after_a_piece(sentence: str, hear: Hear) -> bool:
    await hear(SOUND)
    await anyio.Event().wait()
    await hear(sentence.encode())
    return True


@dataclass(frozen=True)
class Talk:
    say: MemoryObjectSendStream[Event]
    played: ObjectReceiveStream[bytes]
    forwarded: ObjectReceiveStream[tuple[str, bool, str | None]]
    left: ObjectReceiveStream[float]
    reports: list[Report]


@asynccontextmanager
async def talking(
    acknowledgement: Acknowledgement = READY,
    *,
    music: bool = True,
    settle: float = 0.0,
    voice: Voice = voiced,
    unanswered: tuple[str, ...] = (),
) -> AsyncGenerator[Talk]:
    say, events = anyio.create_memory_object_stream[Event](100)
    played_in, played_out = anyio.create_memory_object_stream[bytes](100)
    forwarded_in, forwarded_out = anyio.create_memory_object_stream[tuple[str, bool, str | None]](100)
    left_in, left_out = anyio.create_memory_object_stream[float](100)
    reports: list[Report] = []
    started = anyio.current_time()

    async def claude(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
        await forwarded_in.send((text, interrupted, acknowledgement))

    hold_music = FakeMusic(played=played_in)

    async def leave() -> None:
        await left_in.send(anyio.current_time() - started)

    mouth = Mouth(
        voice=voice,
        speaker=StreamedSpeaker(played_in),
        claude=claude,
        rate=48000,
        clock=lambda: 0.0,
        acknowledgement=acknowledgement,
        understood=understood,
        announcement=announced,
        settle=settle,
        hold_music=hold_music if music else None,
        hold_music_delay=0.0,
        unanswered=unanswered,
        unanswered_after=0.0,
        leave=leave,
        telemetry=reports.append,
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
        yield Talk(say=say, played=played_out, forwarded=forwarded_out, left=left_out, reports=reports)
        tasks.cancel_scope.cancel()


async def test_an_asked_sentence_is_played() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_recording_is_played_as_it_was_recorded() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=(Recording(name="Silent sample.wav", pcm=RECORDED),)))
        played = await talk.played.receive()
    assert played == RECORDED


async def test_a_recording_is_played_after_the_sentence_before_it() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Écoute.", Recording(name="sample.wav", pcm=RECORDED))))
        played = (await talk.played.receive(), await talk.played.receive())
    assert played == (SOUND, RECORDED)


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


async def test_claude_at_work_plays_the_hold_music_after_its_reply() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",)))
        await talk.say.send(ClaudeBusy(at=0.0))
        played = [await talk.played.receive(), await talk.played.receive()]
    assert played == [SOUND, MUSIC]


async def test_the_reply_stops_the_hold_music_before_it_plays() -> None:
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",)))
        await talk.say.send(ClaudeBusy(at=0.0))
        _ = [await talk.played.receive(), await talk.played.receive()]
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = [await talk.played.receive(), await talk.played.receive(), await talk.played.receive()]
    assert played == [b"", FADE, SOUND]


async def test_words_claude_code_never_answered_are_told_it_does_not_answer() -> None:
    async with talking(NOT_READY, music=False, unanswered=("Claude Code ne répond pas.",)) as talk:
        await talk.say.send(Transcribed(text="Tu en es où ?"))
        await talk.say.send(SilenceLasted(ticket=0, at=0.0))
        played = await talk.played.receive()
    assert played == SOUND


async def test_a_second_agent_starting_is_announced() -> None:
    async with talking() as talk:
        await talk.say.send(AgentsChanged(at_work=2))
        played = await talk.played.receive()
    assert played == ANNOUNCEMENT_CLIP


async def test_the_announcement_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking() as talk:
        await talk.say.send(AgentsChanged(at_work=2))
        _ = await talk.played.receive()
    assert "announced 'Two at work.'" in caplog.text


async def test_an_announcement_not_ready_is_not_played() -> None:
    async with talking() as talk:
        await talk.say.send(AgentsChanged(at_work=3))
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = await talk.played.receive()
    assert played == SOUND


async def test_an_announcement_not_ready_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking() as talk:
        await talk.say.send(AgentsChanged(at_work=3))
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        _ = await talk.played.receive()
    assert "no announcement ready for 3 agents at work" in caplog.text


async def test_without_hold_music_claude_at_work_stays_silent() -> None:
    async with talking(music=False) as talk:
        await talk.say.send(Asked(sentences=("Je regarde.",)))
        await talk.say.send(ClaudeBusy(at=0.0))
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


async def reported_after(*events: Event) -> list[Report]:
    async with talking() as talk:
        for event in events:
            await talk.say.send(event)
        await wait_all_tasks_blocked()
    return talk.reports


async def test_a_dismissed_sound_is_reported_at_once() -> None:
    assert await reported_after(SoundDismissed()) == [Counted(name="sound dismissed")]


def forwarded_reports(reports: list[Report]) -> list[Report]:
    return [report for report in reports if isinstance(report, Forwarded | Acknowledged)]


def finished_reports(reports: list[Report]) -> list[Report]:
    return [report for report in reports if isinstance(report, FinishedTurn)]


async def test_a_forwarded_utterance_is_reported_with_what_was_understood_and_its_acknowledgement() -> None:
    reports = await reported_after(SpeechEnded(at=0.0), Transcribed(text="Où en est-on ?"))
    assert forwarded_reports(reports)[0] == Forwarded(
        text="Où en est-on ?", interrupted=False, understood=QUESTION, acknowledgement="Voyons.", voice_end=0.0, at=0.0
    )


async def test_the_acknowledgement_played_is_reported_with_the_words_it_answers() -> None:
    reports = await reported_after(SpeechEnded(at=0.0), Transcribed(text="Où en est-on ?"))
    assert forwarded_reports(reports)[1:] == [Acknowledged(sentence="Voyons.", words="Où en est-on ?", at=0.0)]


async def test_an_utterance_without_a_clip_ready_is_reported_without_acknowledgement() -> None:
    async with talking(NOT_READY) as talk:
        await talk.say.send(Transcribed(text="Le dépôt est propre."))
        _ = await talk.forwarded.receive()
    assert forwarded_reports(talk.reports) == [
        Forwarded(
            text="Le dépôt est propre.",
            interrupted=False,
            understood=NOTHING,
            acknowledgement=None,
            voice_end=0.0,
            at=0.0,
        )
    ]


async def test_the_turn_under_way_is_reported_when_the_conversation_ends() -> None:
    reports = await reported_after(SpeechEnded(at=0.0), Transcribed(text="Bonjour."), SilenceLasted(ticket=0, at=0.0))
    assert finished_reports(reports) == [
        FinishedTurn(
            start=0.0,
            end=0.0,
            steps=(
                Span(name="end of turn", start=0.0, end=0.0),
                Span(name="transcription", start=0.0, end=0.0),
                Span(name="settle", start=0.0, end=0.0),
            ),
            interrupted=False,
        )
    ]


async def test_each_piece_of_a_voice_is_played_as_it_arrives() -> None:
    async with talking(voice=voiced_in_pieces) as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        played = (await talk.played.receive(), await talk.played.receive())
    assert played == (SOUND, b"Bonjour.")


async def test_the_next_sentence_follows_the_whole_voice_of_the_one_before() -> None:
    async with talking(voice=voiced_in_pieces) as talk:
        await talk.say.send(Asked(sentences=("Un.", "Deux.")))
        played = (
            await talk.played.receive(),
            await talk.played.receive(),
            await talk.played.receive(),
            await talk.played.receive(),
        )
    assert played == (SOUND, b"Un.", SOUND, b"Deux.")


async def test_a_voice_broken_after_a_piece_moves_on_to_the_next_sentence() -> None:
    async with talking(voice=broken_after_a_piece) as talk:
        await talk.say.send(Asked(sentences=("Broken sentence.", "Spoken sentence.")))
        played = (await talk.played.receive(), await talk.played.receive())
    assert played == (SOUND, SOUND)


async def test_an_interruption_cancels_the_voice_still_arriving(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking(voice=hanging_after_a_piece) as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        _ = await talk.played.receive()
        await talk.say.send(VoiceDetected(at=0.0))
        _ = await talk.played.receive()
        await wait_all_tasks_blocked()
    assert "synthesis 0 cancelled" in caplog.text


async def test_the_first_audio_of_a_sentence_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        _ = await talk.played.receive()
        await wait_all_tasks_blocked()
    assert "first audio in 0.00 s: 'Bonjour.'" in caplog.text


async def test_the_whole_voice_of_a_sentence_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    async with talking() as talk:
        await talk.say.send(Asked(sentences=("Bonjour.",)))
        _ = await talk.played.receive()
        await wait_all_tasks_blocked()
    assert "voice in 0.00 s for 0.1 s of speech: 'Bonjour.'" in caplog.text
