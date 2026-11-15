import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx
import numpy as np
import pytest
import stamina

from voice_bridge.features.speaking.abilities.speak.domain.ports import Pace, Pacing
from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import (
    SpeechEngine,
    SynthesisError,
    is_ready,
    stream,
    synthesize,
    wait_until_ready,
)
from voice_bridge.libraries.audio.wav import encode

pytestmark = pytest.mark.anyio

REFUSED = "connection refused"
SAMPLES = np.array([1000, -1000], dtype=np.int16).tobytes()
OTHER_SAMPLES = np.array([500, -500], dtype=np.int16).tobytes()
TENTH_OF_A_SECOND_AT_24_KHZ = bytes(4800)


@dataclass(frozen=True)
class KeptPace:
    def push(self, pcm: bytes) -> bytes:
        return pcm

    def end(self) -> bytes:
        return b""


@dataclass(frozen=True)
class HalvedPace:
    def push(self, pcm: bytes) -> bytes:
        return pcm[: len(pcm) // 2]

    def end(self) -> bytes:
        return b""


@dataclass(frozen=True)
class TailedPace:
    def push(self, pcm: bytes) -> bytes:
        return pcm

    def end(self) -> bytes:
        return SAMPLES


def unchanged(_rate: int, _factor: float) -> Pace:
    return KeptPace()


def halved(_rate: int, _factor: float) -> Pace:
    return HalvedPace()


def tailed(_rate: int, _factor: float) -> Pace:
    return TailedPace()


@dataclass
class WatchedPacing:
    asked: list[tuple[int, float]] = field(default_factory=list)

    def __call__(self, rate: int, factor: float) -> Pace:
        self.asked.append((rate, factor))
        return KeptPace()


def engine(
    handler: httpx.MockTransport,
    gain: float = 1.0,
    health: str = "/health",
    speed: float = 1.0,
    pacing: Pacing = unchanged,
) -> SpeechEngine:
    return SpeechEngine(
        client=httpx.AsyncClient(transport=handler, base_url="http://speech"),
        model="mistralai/Voxtral-4B-TTS-2603",
        voice="fr_female",
        gain=gain,
        speed=speed,
        pacing=pacing,
        rate=48000,
        health=health,
    )


def answering_wav(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=encode(SAMPLES, rate=48000), request=request)


SPEECH_REQUEST = {
    "model": "mistralai/Voxtral-4B-TTS-2603",
    "input": "Bonjour.",
    "voice": "fr_female",
    "response_format": "wav",
}


def answering_only_the_speech_request(request: httpx.Request) -> httpx.Response:
    expected = request.url.path == "/v1/audio/speech" and json.loads(request.content) == SPEECH_REQUEST
    return answering_wav(request) if expected else httpx.Response(400, request=request)


def answering_at_24_khz(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=encode(TENTH_OF_A_SECOND_AT_24_KHZ, rate=24000), request=request)


def failing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, request=request)


def refusing(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(REFUSED, request=request)


def healthy(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200 if request.url.path == "/health" else 404)


async def test_synthesis_returns_the_audio_of_the_sentence() -> None:
    assert await synthesize(engine(httpx.MockTransport(answering_wav)), "Bonjour.") == SAMPLES


async def test_synthesis_applies_the_gain() -> None:
    assert await synthesize(engine(httpx.MockTransport(answering_wav), gain=2.0), "Bonjour.") != SAMPLES


async def test_synthesis_asks_the_openai_compatible_speech_endpoint() -> None:
    assert await synthesize(engine(httpx.MockTransport(answering_only_the_speech_request)), "Bonjour.") == SAMPLES


async def test_synthesis_leaves_the_pace_to_the_bridge_instead_of_the_server() -> None:
    faster = engine(httpx.MockTransport(answering_only_the_speech_request), speed=1.2)
    assert await synthesize(faster, "Bonjour.") == SAMPLES


async def test_synthesis_stretches_the_audio_at_the_rate_of_the_server_by_the_speed() -> None:
    pacing = WatchedPacing()
    _ = await synthesize(engine(httpx.MockTransport(answering_at_24_khz), speed=1.2, pacing=pacing), "Bonjour.")
    assert pacing.asked == [(24000, 1.2)]


async def test_synthesis_resamples_the_stretched_audio_to_the_rate_of_the_engine() -> None:
    pcm = await synthesize(engine(httpx.MockTransport(answering_at_24_khz), pacing=halved), "Bonjour.")
    assert len(pcm) == len(TENTH_OF_A_SECOND_AT_24_KHZ)


async def test_a_server_error_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await synthesize(engine(httpx.MockTransport(failing)), "Bonjour.")


async def test_an_unreachable_server_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await synthesize(engine(httpx.MockTransport(refusing)), "Bonjour.")


async def test_synthesis_keeps_the_audio_the_pace_gives_back_at_its_end() -> None:
    assert await synthesize(engine(httpx.MockTransport(answering_wav), pacing=tailed), "Bonjour.") == SAMPLES * 2


async def pieces(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def broken_after(chunk: bytes) -> AsyncIterator[bytes]:
    yield chunk
    raise httpx.ReadError(REFUSED)


STREAM_REQUEST = {**SPEECH_REQUEST, "response_format": "pcm", "stream": True, "stream_format": "audio"}


def streaming(*chunks: bytes, rate: str | None = "48000") -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        expected = request.url.path == "/v1/audio/speech" and json.loads(request.content) == STREAM_REQUEST
        headers = {} if rate is None else {"X-Audio-Sample-Rate": rate}
        return httpx.Response(200 if expected else 400, headers=headers, content=pieces(*chunks), request=request)

    return httpx.MockTransport(answer)


def breaking_after(chunk: bytes) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"X-Audio-Sample-Rate": "48000"}, content=broken_after(chunk), request=request
        )
    )


@dataclass
class Ear:
    heard: list[bytes] = field(default_factory=list)

    async def __call__(self, pcm: bytes) -> None:
        self.heard.append(pcm)


async def heard_from(speech: SpeechEngine) -> list[bytes]:
    ear = Ear()
    await stream(speech, "Bonjour.", ear)
    return ear.heard


async def test_a_streamed_voice_is_heard_piece_by_piece() -> None:
    assert await heard_from(engine(streaming(SAMPLES, OTHER_SAMPLES))) == [SAMPLES, OTHER_SAMPLES]


async def test_a_piece_cut_inside_a_sample_is_heard_once_the_sample_is_whole() -> None:
    assert await heard_from(engine(streaming(SAMPLES[:1], SAMPLES[1:]))) == [SAMPLES]


async def test_the_streamed_voice_gets_the_gain() -> None:
    assert await heard_from(engine(streaming(SAMPLES), gain=2.0)) != [SAMPLES]


async def test_the_audio_the_pace_gives_back_at_the_end_is_heard_last() -> None:
    assert await heard_from(engine(streaming(OTHER_SAMPLES), pacing=tailed)) == [OTHER_SAMPLES, SAMPLES]


async def test_the_streamed_voice_is_paced_at_the_rate_the_server_names_by_the_speed() -> None:
    pacing = WatchedPacing()
    _ = await heard_from(engine(streaming(SAMPLES, rate="24000"), speed=1.2, pacing=pacing))
    assert pacing.asked == [(24000, 1.2)]


async def test_a_server_naming_no_rate_streams_at_24_khz() -> None:
    pacing = WatchedPacing()
    _ = await heard_from(engine(streaming(SAMPLES, rate=None), pacing=pacing))
    assert pacing.asked == [(24000, 1.0)]


async def test_the_streamed_voice_is_resampled_to_the_rate_of_the_engine() -> None:
    heard = await heard_from(engine(streaming(TENTH_OF_A_SECOND_AT_24_KHZ, rate="24000")))
    assert len(b"".join(heard)) == len(TENTH_OF_A_SECOND_AT_24_KHZ) * 2


async def test_a_refused_stream_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await heard_from(engine(httpx.MockTransport(failing)))


async def test_a_rate_that_is_not_a_number_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await heard_from(engine(streaming(SAMPLES, rate="fast")))


async def test_a_stream_broken_midway_is_a_synthesis_error_after_the_voice_already_heard() -> None:
    ear = Ear()
    with pytest.raises(SynthesisError):
        await stream(engine(breaking_after(SAMPLES)), "Bonjour.", ear)
    assert ear.heard == [SAMPLES]


async def test_the_server_is_ready_when_its_health_answers() -> None:
    assert await is_ready(engine(httpx.MockTransport(healthy)))


async def test_the_server_is_not_ready_when_unreachable() -> None:
    assert not await is_ready(engine(httpx.MockTransport(refusing)))


async def test_waiting_for_a_ready_server_returns_at_once() -> None:
    assert await wait_until_ready(engine(httpx.MockTransport(healthy))) is None


def ready_on_second_call() -> httpx.MockTransport:
    answers = iter([httpx.Response(503), httpx.Response(200)])
    return httpx.MockTransport(lambda _request: next(answers))


async def test_waiting_retries_until_the_server_is_ready() -> None:
    with stamina.set_testing(True, attempts=2):
        assert await wait_until_ready(engine(ready_on_second_call())) is None


def answering_on(path: str) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200 if request.url.path == path else 404))


async def test_the_health_route_can_be_set_for_another_engine() -> None:
    assert await is_ready(engine(answering_on("/v1/models"), health="/v1/models"))


async def test_an_engine_without_a_health_route_is_ready_at_once() -> None:
    assert await is_ready(engine(httpx.MockTransport(refusing), health=""))
