import logging
import math
import time
from functools import partial
from typing import TYPE_CHECKING, Final, assert_never

import anyio
import httpx
from faster_whisper import WhisperModel
from faster_whisper.vad import get_vad_model
from pymumble_rev.audio import PcmBuffer

from voice_bridge.features.conversation.abilities.hold_conversation import Claude, Mouth, hold_conversation
from voice_bridge.features.conversation.domain.turn_taking import Asked, Event, Transcribed, VoiceDetected
from voice_bridge.features.hearing.abilities.listen import Ears, Heard, Speaking, Turn, TurnChecked, Utterance, listen
from voice_bridge.features.hearing.abilities.transcribe import Transcription, transcribe_utterances
from voice_bridge.features.hearing.domain.noise import Hallucinations
from voice_bridge.features.hearing.domain.utterance import Dismissed, UtteranceRules
from voice_bridge.features.hearing.implementations.silero import Voicing
from voice_bridge.features.hearing.implementations.smart_turn import completion, load_session
from voice_bridge.features.speaking.abilities.acknowledge import Acknowledgements, Clips, record_acknowledgements
from voice_bridge.features.speaking.abilities.speak import sentences_of, voice_of
from voice_bridge.features.speaking.implementations.voxtral import Voxtral, wait_until_ready
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

    from anyio.abc import ObjectReceiveStream
    from pymumble_rev import MumbleClient

    from voice_bridge.configuration.language import LanguagePack
    from voice_bridge.configuration.settings import Settings

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
        session=get_vad_model().session,
        voicing=Voicing(volume_threshold=hearing.volume_threshold, probability=hearing.voice_probability),
        rules=UtteranceRules(
            silence=hearing.silence,
            longest=hearing.longest,
            shortest_voice=hearing.shortest_voice,
            preroll=hearing.preroll,
            barge_in=hearing.barge_in,
            barge_window=hearing.barge_window,
            short_pause=hearing.short_pause if hearing.smart_turn else None,
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


async def converse(
    settings: Settings, language: LanguagePack, claude: Claude, replies: ObjectReceiveStream[str], username: str
) -> None:
    events_in, events_out = anyio.create_memory_object_stream[Event](math.inf)
    packets_in, packets_out = anyio.create_memory_object_stream[Packet](math.inf)
    utterances_in, utterances_out = anyio.create_memory_object_stream[bytes](math.inf)
    buffer = PcmBuffer(channels=1, capacity=PLAYBACK_CAPACITY)
    transcription = await _transcription(settings, language)
    voxtral_settings = settings.voxtral

    async def connected(client: MumbleClient) -> None:
        _ = client.play(buffer)
        await pump_audio(
            client, holds_certificate(settings.mumble.speaker_certificate_hash), packets_in, anyio.current_time
        )

    async def heard(each: Heard) -> None:
        match each:
            case Speaking(at=at):
                await events_in.send(VoiceDetected(at=at))
            case Utterance(pcm=pcm):
                await utterances_in.send(pcm)
            case Dismissed() | TurnChecked():
                _log_hearing(each, settings.hearing.silence)
            case _:
                assert_never(each)

    async def transcribed(text: str, *, noise: bool) -> None:
        await events_in.send(Transcribed(text=text, noise=noise))

    async def relay_replies() -> None:
        async for text in replies:
            await events_in.send(Asked(sentences=sentences_of(text)))

    async with (
        events_in,
        events_out,
        packets_in,
        packets_out,
        utterances_in,
        utterances_out,
        httpx.AsyncClient(base_url=str(voxtral_settings.url), timeout=voxtral_settings.timeout) as http,
        anyio.create_task_group() as tasks,
    ):
        voxtral = Voxtral(
            client=http,
            model=voxtral_settings.model,
            voice=voxtral_settings.voice or language.voice,
            gain=voxtral_settings.gain,
            rate=MUMBLE_RATE,
        )
        clips = Clips()
        mouth = Mouth(
            voice=partial(voice_of, voxtral),
            speaker=Loudspeaker(buffer=buffer),
            claude=claude,
            rate=MUMBLE_RATE,
            clock=anyio.current_time,
            acknowledgement=clips,
        )

        async def greet() -> None:
            await wait_until_ready(voxtral)
            await events_in.send(Asked(sentences=sentences_of(language.greeting)))
            await record_acknowledgements(
                clips,
                partial(voice_of, voxtral),
                Acknowledgements(
                    questions=language.question_acknowledgements, statements=language.statement_acknowledgements
                ),
            )

        _ = tasks.start_soon(stay_connected, access(settings, username), connected)
        _ = tasks.start_soon(listen, _ears(settings), with_pauses(packets_out, PATIENCE), heard, anyio.current_time)
        _ = tasks.start_soon(transcribe_utterances, transcription, utterances_out, transcribed)
        _ = tasks.start_soon(hold_conversation, mouth, events_out, events_in.clone())
        _ = tasks.start_soon(relay_replies)
        _ = tasks.start_soon(greet)
