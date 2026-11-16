import logging
import math
import os
import secrets
import signal
import time
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Final, assert_never

import anyio
import httpx
from faster_whisper import WhisperModel
from pymumble_rev.audio import PcmBuffer

from voice_bridge.configuration.log_config import kept_days
from voice_bridge.configuration.telemetry import run_attributes
from voice_bridge.entrypoints.telemetry import chosen_telemetry
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    News,
    listen_to_claude,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.hold_conversation import (
    Mouth,
    hold_conversation,
)
from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Event,
    SoundDismissed,
    SpeechEnded,
    SpeechStarted,
    Transcribed,
    VoiceDetected,
)
from voice_bridge.features.conversation.domain.turn_trace import Understood
from voice_bridge.features.hearing.abilities.listen.domain.heard import (
    Heard,
    Speaking,
    Turn,
    TurnChecked,
    Utterance,
    VoiceStarted,
)
from voice_bridge.features.hearing.abilities.listen.domain.voicing import Voicing
from voice_bridge.features.hearing.abilities.listen.implementation.listen import Ears, listen
from voice_bridge.features.hearing.abilities.listen.implementation.silero import SileroDetector, load_silero
from voice_bridge.features.hearing.abilities.listen.implementation.smart_turn import completion, load_session
from voice_bridge.features.hearing.abilities.transcribe.implementation.transcribe import (
    Transcription,
    transcribe_utterances,
)
from voice_bridge.features.hearing.domain.noise import Hallucinations
from voice_bridge.features.hearing.domain.utterance import Dismissed, UtteranceRules
from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import fallback, pool_of
from voice_bridge.features.speaking.abilities.acknowledge.implementation.acknowledge import (
    Clips,
    record_acknowledgements,
)
from voice_bridge.features.speaking.abilities.acknowledge.implementation.clip_cache import CachedVoice
from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording
from voice_bridge.features.speaking.abilities.announce.implementation.announce import (
    Announcements,
    record_announcements,
)
from voice_bridge.features.speaking.abilities.hold_music.implementation.hold_music import HoldMusic, track_of
from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import SpeechEngine, wait_until_ready
from voice_bridge.features.speaking.abilities.speak.implementation.speak import (
    sentences_of,
    voice_of,
    voice_streamed,
)
from voice_bridge.features.understanding.abilities.understand.implementation.embeddings import load_encoder, router
from voice_bridge.features.understanding.abilities.understand.implementation.understand import StopFlag, Understanding
from voice_bridge.features.understanding.domain.meaning import Route
from voice_bridge.libraries.audio.file import decode_audio
from voice_bridge.libraries.audio.tempo import METHOD as PACE_METHOD
from voice_bridge.libraries.audio.tempo import pace
from voice_bridge.libraries.mumble.audio import (
    MUMBLE_RATE,
    Loudspeaker,
    Packet,
    holds_certificate,
    pump_audio,
    with_pauses,
)
from voice_bridge.libraries.mumble.connection import Access, stay_connected

if TYPE_CHECKING:
    from collections.abc import Callable

    from anyio.abc import ObjectReceiveStream, ObjectSendStream
    from pymumble_rev import MumbleClient

    from voice_bridge.configuration.language import LanguagePack
    from voice_bridge.configuration.settings import Settings
    from voice_bridge.features.conversation.abilities.hold_conversation.domain.ports import Claude, Interpreter
    from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_channel import Reply
    from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard

logger = logging.getLogger(__name__)

PLAYBACK_CAPACITY: Final = 600.0
PATIENCE: Final = 0.05


def access(settings: Settings, username: str) -> Access:
    return Access(
        host=settings.mumble.host,
        port=settings.mumble.port,
        username=username,
        password=settings.mumble.password.get_secret_value(),
        server_certificate=settings.mumble.server_certificate,
    )


def _timed(judge: Callable[[bytes], float]) -> Callable[[bytes], float]:
    def timed(pcm: bytes) -> float:
        started = time.perf_counter()
        probability = judge(pcm)
        logger.info("end of turn judged in %.0f ms", (time.perf_counter() - started) * 1000)
        return probability

    return timed


def _turn(settings: Settings) -> Turn | None:
    hearing = settings.hearing
    if not hearing.smart_turn:
        return None
    return Turn(judge=_timed(partial(completion, load_session(), rate=MUMBLE_RATE)), threshold=hearing.turn_threshold)


def _log_hearing(each: Dismissed | TurnChecked, silence: float) -> None:
    match each:
        case Dismissed(voice=voice, duration=lasted):
            logger.info("dismissed a sound of %.2f s holding %.2f s of voice", lasted, voice)
        case TurnChecked(probability=probability, pause=pause, finished=True):
            logger.info(
                "turn finished (p=%.2f) after %.2f s of silence, %.2f s sooner than the silence rule",
                probability,
                pause,
                silence - pause,
            )
        case TurnChecked(probability=probability, pause=pause):
            logger.info("turn not finished (p=%.2f) after %.2f s of silence", probability, pause)
        case _:
            assert_never(each)


def _ears(settings: Settings) -> Ears:
    hearing = settings.hearing
    return Ears(
        detector=SileroDetector(session=load_silero(), rate=MUMBLE_RATE),
        voicing=Voicing(volume_threshold=hearing.volume_threshold, probability=hearing.voice_probability),
        rules=UtteranceRules(
            silence=hearing.silence,
            longest=hearing.longest,
            shortest_voice=hearing.shortest_voice,
            preroll=hearing.preroll,
            barge_in=hearing.barge_in,
            barge_window=hearing.barge_window,
            short_pause=hearing.short_pause if hearing.smart_turn else None,
            unfinished_silence=hearing.unfinished_silence if hearing.smart_turn else None,
        ),
        rate=MUMBLE_RATE,
        turn=_turn(settings),
    )


async def _transcription(settings: Settings, language: LanguagePack) -> Transcription:
    whisper = settings.whisper
    model = await anyio.to_thread.run_sync(
        partial(WhisperModel, whisper.model, device=whisper.device, compute_type=whisper.compute_type)
    )
    hallucinations = Hallucinations(texts=language.hallucinations, prefixes=language.hallucination_prefixes)
    return Transcription(model=model, rate=MUMBLE_RATE, language=language.whisper_code, hallucinations=hallucinations)


async def _route(
    each: Heard, events: ObjectSendStream[Event], utterances: ObjectSendStream[bytes], silence: float
) -> None:
    match each:
        case VoiceStarted(at=at):
            await events.send(SpeechStarted(at=at))
        case Speaking(at=at):
            await events.send(VoiceDetected(at=at))
        case Utterance(pcm=pcm, ended=ended):
            await events.send(SpeechEnded(at=ended))
            await utterances.send(pcm)
        case Dismissed():
            _log_hearing(each, silence)
            await events.send(SoundDismissed())
        case TurnChecked():
            _log_hearing(each, silence)
        case _:
            assert_never(each)


async def _hold_music(settings: Settings, speaker: Loudspeaker) -> HoldMusic | None:
    hold_music = settings.hold_music
    if hold_music.file is None:
        return None
    track = await anyio.to_thread.run_sync(
        partial(track_of, hold_music.file, decode=decode_audio, rate=MUMBLE_RATE, volume=hold_music.volume)
    )
    logger.info("hold music ready: %s, %.0f s", hold_music.file.name, len(track.pcm) / 2 / MUMBLE_RATE)
    return HoldMusic(
        track=track,
        speaker=speaker,
        rate=MUMBLE_RATE,
        fade_in=hold_music.fade_in,
        fade_out=hold_music.fade_out,
    )


def _understanding(settings: Settings, language: LanguagePack) -> Understanding:
    routes = language.acknowledgements
    understanding = Understanding(
        scores=router(load_encoder(), [route.examples for route in routes]),
        routes=tuple(
            Route(
                name=route.name,
                threshold=settings.understanding.threshold if route.threshold is None else route.threshold,
                stops=route.stops,
                answers=route.answers,
            )
            for route in routes
        ),
    )
    logger.info("%d routes understood from %d examples", len(routes), sum(len(route.examples) for route in routes))
    return understanding


def _interpreting(understanding: Understanding) -> Interpreter:
    def interpret(words: str) -> Understood:
        meaning = understanding(words)
        if meaning.route is None:
            return Understood(route=None, ranking=meaning.ranking, fallback=fallback(words))
        return Understood(route=understanding.routes[meaning.route].name, ranking=meaning.ranking)

    return interpret


def _wording(language: LanguagePack) -> Wording:
    announcements = language.announcements
    return Wording(at_work=announcements.at_work, many_at_work=announcements.many_at_work)


async def _end_claude_code(pid: int | None) -> None:
    if pid is None:
        logger.warning("no Claude Code process to end: start the bridge with scripts/claude-voice.sh")
        return
    logger.info("ending Claude Code, process %d", pid)
    os.kill(pid, signal.SIGTERM)


def _following_stops(claude: Claude, understanding: Understanding, flag: StopFlag) -> Claude:
    async def forward(text: str, *, interrupted: bool, acknowledgement: str | None) -> None:
        flag.follow(understanding(text))
        await claude(text, interrupted=interrupted, acknowledgement=acknowledgement)

    return forward


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaudeSide:
    claude: Claude
    replies: ObjectReceiveStream[Reply]
    board: WorkBoard


async def converse(settings: Settings, language: LanguagePack, side: ClaudeSide, username: str) -> None:
    events_in, events_out = anyio.create_memory_object_stream[Event](math.inf)
    packets_in, packets_out = anyio.create_memory_object_stream[Packet](math.inf)
    utterances_in, utterances_out = anyio.create_memory_object_stream[bytes](math.inf)
    buffer = PcmBuffer(channels=1, capacity=PLAYBACK_CAPACITY)
    transcription = await _transcription(settings, language)
    speaker = Loudspeaker(buffer=buffer)
    hold_music = await _hold_music(settings, speaker)
    understanding = await anyio.to_thread.run_sync(_understanding, settings, language)
    speech_settings = settings.speech
    telemetry, stalled_for = chosen_telemetry(
        anyio.current_time,
        settings.telemetry_directory,
        kept_days(settings.telemetry_retention),
        run_attributes(settings, voice=speech_settings.voice or language.voice, pace=PACE_METHOD),
    )

    async def connected(client: MumbleClient) -> None:
        _ = client.play(buffer)
        await pump_audio(
            client,
            holds_certificate(settings.mumble.speaker_certificate_hash),
            packets_in,
            anyio.current_time,
            stalled_for,
        )

    async def heard(each: Heard) -> None:
        await _route(each, events_in, utterances_in, settings.hearing.silence)

    async def transcribed(text: str, *, noise: bool) -> None:
        meaning = None if noise else understanding(text)
        stops = meaning is not None and meaning.stops
        answered = meaning is not None and meaning.answers
        await events_in.send(
            Transcribed(text=text, noise=noise, stop_at=anyio.current_time() if stops else None, answered=answered)
        )

    async def claude_is(news: News) -> None:
        for event in side.board.events_of(news, anyio.current_time()):
            await events_in.send(event)

    async def relay_replies() -> None:
        async for reply in side.replies:
            recordings = () if reply.recording is None else (reply.recording,)
            await events_in.send(Asked(sentences=(*sentences_of(reply.text), *recordings), ending=reply.ending))

    async with (
        events_in,
        events_out,
        packets_in,
        packets_out,
        utterances_in,
        utterances_out,
        httpx.AsyncClient(base_url=str(speech_settings.url), timeout=speech_settings.timeout) as http,
        anyio.create_task_group() as tasks,
    ):
        engine = SpeechEngine(
            client=http,
            model=speech_settings.model,
            voice=speech_settings.voice or language.voice,
            gain=speech_settings.gain,
            speed=speech_settings.speed,
            pacing=pace,
            rate=MUMBLE_RATE,
            health=speech_settings.health,
        )
        greeting = secrets.choice(language.greetings)
        clips = Clips(
            draw=secrets.choice,
            kind=lambda words: pool_of(understanding(words).route, words, routes=len(language.acknowledgements)),
            last=greeting,
        )
        announcements = Announcements(wording=_wording(language))
        mouth = Mouth(
            voice=partial(voice_streamed, engine),
            speaker=speaker,
            claude=_following_stops(side.claude, understanding, StopFlag(settings.understanding.stop_flag)),
            rate=MUMBLE_RATE,
            clock=anyio.current_time,
            acknowledgement=clips,
            understood=_interpreting(understanding),
            announcement=announcements,
            settle=settings.hearing.settle,
            hold_music=hold_music,
            hold_music_delay=settings.hold_music.delay,
            unanswered=sentences_of(language.unanswered),
            unanswered_after=settings.claude.unanswered_after,
            leave=partial(_end_claude_code, settings.claude_pid),
            telemetry=telemetry,
        )

        def cached(directory: str) -> CachedVoice:
            return CachedVoice(
                voice=partial(voice_of, engine),
                directory=settings.cache_directory / directory,
                key=f"{engine.model} {engine.voice} {engine.gain} {engine.speed} {PACE_METHOD} {MUMBLE_RATE}",
            )

        async def greet() -> None:
            await wait_until_ready(engine)
            await events_in.send(Asked(sentences=sentences_of(greeting)))
            acknowledging = cached("acknowledgements")
            await record_acknowledgements(
                clips,
                acknowledging,
                [
                    *(route.sentences for route in language.acknowledgements),
                    language.neutral_acknowledgements,
                    language.neutral_question_acknowledgements,
                ],
            )
            await acknowledging.prune()
            announcing = cached("announcements")
            await record_announcements(announcements, announcing)
            await announcing.prune()

        _ = tasks.start_soon(stay_connected, access(settings, username), connected)
        _ = tasks.start_soon(listen, _ears(settings), with_pauses(packets_out, PATIENCE), heard, anyio.current_time)
        _ = tasks.start_soon(transcribe_utterances, transcription, utterances_out, transcribed)
        _ = tasks.start_soon(hold_conversation, mouth, events_out, events_in.clone())
        _ = tasks.start_soon(relay_replies)
        _ = tasks.start_soon(listen_to_claude, settings.activity_socket, claude_is)
        _ = tasks.start_soon(greet)
