import json
import socket
from collections.abc import AsyncIterator, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from typing import cast

import anyio
import httpx
import numpy as np
import pytest

from voice_bridge.features.speaking.abilities.speak.domain.ports import Pace, Pacing, Synthesis, SynthesisError
from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import OpenAICompatibleSpeech, client
from voice_bridge.libraries.audio.wav import encode

pytestmark = pytest.mark.anyio

REFUSED = "connection refused"
SAMPLES = np.array([1000, -1000], dtype=np.int16).tobytes()
OTHER_SAMPLES = np.array([500, -500], dtype=np.int16).tobytes()
TENTH_OF_A_SECOND_AT_24_KHZ = bytes(4800)
WHOLE_TIMEOUT = 120.0
SHORT_TIMEOUT = 0.1
LONGER_THAN_THE_SHORT_TIMEOUT = 0.3
LONG_TIMEOUT = 10.0


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
) -> OpenAICompatibleSpeech:
    return OpenAICompatibleSpeech(
        client=httpx.AsyncClient(transport=handler, base_url="http://speech"),
        model="mistralai/Voxtral-4B-TTS-2603",
        voice="fr_female",
        gain=gain,
        speed=speed,
        pacing=pacing,
        rate=48000,
        health=health,
        first_audio_timeout=WHOLE_TIMEOUT,
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
    assert await engine(httpx.MockTransport(answering_wav)).whole("Bonjour.") == SAMPLES


async def test_synthesis_applies_the_gain() -> None:
    assert await engine(httpx.MockTransport(answering_wav), gain=2.0).whole("Bonjour.") != SAMPLES


async def test_synthesis_asks_the_openai_compatible_speech_endpoint() -> None:
    assert await engine(httpx.MockTransport(answering_only_the_speech_request)).whole("Bonjour.") == SAMPLES


async def test_synthesis_leaves_the_pace_to_the_bridge_instead_of_the_server() -> None:
    faster = engine(httpx.MockTransport(answering_only_the_speech_request), speed=1.2)
    assert await faster.whole("Bonjour.") == SAMPLES


async def test_synthesis_stretches_the_audio_at_the_rate_of_the_server_by_the_speed() -> None:
    pacing = WatchedPacing()
    _ = await engine(httpx.MockTransport(answering_at_24_khz), speed=1.2, pacing=pacing).whole("Bonjour.")
    assert pacing.asked == [(24000, 1.2)]


async def test_synthesis_resamples_the_stretched_audio_to_the_rate_of_the_engine() -> None:
    pcm = await engine(httpx.MockTransport(answering_at_24_khz), pacing=halved).whole("Bonjour.")
    assert len(pcm) == len(TENTH_OF_A_SECOND_AT_24_KHZ)


async def test_a_server_error_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await engine(httpx.MockTransport(failing)).whole("Bonjour.")


async def test_an_unreachable_server_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await engine(httpx.MockTransport(refusing)).whole("Bonjour.")


async def test_synthesis_keeps_the_audio_the_pace_gives_back_at_its_end() -> None:
    assert await engine(httpx.MockTransport(answering_wav), pacing=tailed).whole("Bonjour.") == SAMPLES * 2


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


async def heard_from(speech: OpenAICompatibleSpeech) -> list[bytes]:
    ear = Ear()
    await speech.stream("Bonjour.", ear)
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
        await engine(breaking_after(SAMPLES)).stream("Bonjour.", ear)
    assert ear.heard == [SAMPLES]


@contextmanager
def listening(backlog: int) -> Generator[socket.socket]:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(backlog)
        yield server


def address_of(server: socket.socket) -> tuple[str, int]:
    return cast("tuple[str, int]", server.getsockname())


def knocking(server: socket.socket, stack: ExitStack) -> None:
    knock = stack.enter_context(socket.socket())
    knock.settimeout(0.0)
    _ = knock.connect_ex(address_of(server))


def url_of(server: socket.socket) -> str:
    host, port = address_of(server)
    return f"http://{host}:{port}"


@contextmanager
def unreachable() -> Generator[str]:
    with listening(0) as server, ExitStack() as stack:
        knocking(server, stack)
        knocking(server, stack)
        yield url_of(server)


@contextmanager
def accepting_but_silent() -> Generator[str]:
    with listening(8) as server:
        yield url_of(server)


async def held_before(*chunks: bytes) -> AsyncIterator[bytes]:
    await anyio.sleep(LONGER_THAN_THE_SHORT_TIMEOUT)
    for chunk in chunks:
        yield chunk


async def pausing_after(first: bytes, then: bytes) -> AsyncIterator[bytes]:
    yield first
    await anyio.sleep(LONGER_THAN_THE_SHORT_TIMEOUT)
    yield then


def answering_with(content: AsyncIterator[bytes]) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"X-Audio-Sample-Rate": "48000"}, content=content, request=request)
    )


async def answering_late(request: httpx.Request) -> httpx.Response:
    await anyio.sleep(SHORT_TIMEOUT)
    return httpx.Response(200, headers={"X-Audio-Sample-Rate": "48000"}, content=pieces(SAMPLES), request=request)


def waiting_long_for_the_first_audio(url: str, connect_timeout: float) -> OpenAICompatibleSpeech:
    return replace(SPEECH, client=client(url, timeout=WHOLE_TIMEOUT, connect_timeout=connect_timeout))


def waiting_long_for_the_connection(url: str) -> OpenAICompatibleSpeech:
    return replace(
        SPEECH,
        client=client(url, timeout=WHOLE_TIMEOUT, connect_timeout=WHOLE_TIMEOUT),
        first_audio_timeout=SHORT_TIMEOUT,
    )


async def test_an_unreachable_server_gives_up_the_sentence_after_the_connect_timeout() -> None:
    with unreachable() as url, anyio.fail_after(LONG_TIMEOUT), pytest.raises(SynthesisError):
        _ = await heard_from(waiting_long_for_the_first_audio(url, connect_timeout=SHORT_TIMEOUT))


async def test_an_unreachable_server_gives_up_the_whole_voice_after_the_connect_timeout() -> None:
    with unreachable() as url, anyio.fail_after(LONG_TIMEOUT), pytest.raises(SynthesisError):
        _ = await waiting_long_for_the_first_audio(url, connect_timeout=SHORT_TIMEOUT).whole("Bonjour.")


async def test_a_server_that_accepts_but_never_answers_gives_up_the_sentence_after_the_first_audio_timeout() -> None:
    with accepting_but_silent() as url, anyio.fail_after(LONG_TIMEOUT), pytest.raises(SynthesisError):
        _ = await heard_from(waiting_long_for_the_connection(url))


async def test_a_server_that_answers_without_audio_gives_up_the_sentence_after_the_first_audio_timeout() -> None:
    speech = replace(engine(answering_with(held_before(SAMPLES))), first_audio_timeout=SHORT_TIMEOUT)
    with anyio.fail_after(LONG_TIMEOUT), pytest.raises(SynthesisError):
        _ = await heard_from(speech)


async def test_a_slow_server_whose_first_audio_comes_in_time_is_heard() -> None:
    speech = replace(engine(httpx.MockTransport(answering_late)), first_audio_timeout=LONG_TIMEOUT)
    assert await heard_from(speech) == [SAMPLES]


async def test_a_pause_after_the_first_audio_longer_than_the_first_audio_timeout_is_heard_whole() -> None:
    speech = replace(engine(answering_with(pausing_after(SAMPLES, OTHER_SAMPLES))), first_audio_timeout=SHORT_TIMEOUT)
    assert await heard_from(speech) == [SAMPLES, OTHER_SAMPLES]


async def test_the_server_is_ready_when_its_health_answers() -> None:
    assert await engine(httpx.MockTransport(healthy)).ready()


async def test_the_server_is_not_ready_when_unreachable() -> None:
    assert not await engine(httpx.MockTransport(refusing)).ready()


def answering_on(path: str) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200 if request.url.path == path else 404))


async def test_the_health_route_can_be_set_for_another_engine() -> None:
    assert await engine(answering_on("/v1/models"), health="/v1/models").ready()


async def test_an_engine_without_a_health_route_is_ready_at_once() -> None:
    assert await engine(httpx.MockTransport(refusing), health="").ready()


async def test_the_openai_compatible_client_is_a_synthesis() -> None:
    synthesis: Synthesis = engine(httpx.MockTransport(answering_wav))
    assert await synthesis.whole("Bonjour.") == SAMPLES


ANSWERING = httpx.MockTransport(answering_wav)
SPEECH = engine(ANSWERING)


async def test_the_fingerprint_names_the_adapter_so_another_engine_never_shares_its_clips() -> None:
    assert SPEECH.fingerprint.startswith("openai-compatible ")


async def test_another_model_changes_the_fingerprint() -> None:
    assert replace(SPEECH, model="other").fingerprint != SPEECH.fingerprint


async def test_another_voice_changes_the_fingerprint() -> None:
    assert replace(SPEECH, voice="en_male").fingerprint != SPEECH.fingerprint


async def test_another_gain_changes_the_fingerprint() -> None:
    assert replace(SPEECH, gain=2.0).fingerprint != SPEECH.fingerprint


async def test_another_speed_changes_the_fingerprint() -> None:
    assert replace(SPEECH, speed=1.2).fingerprint != SPEECH.fingerprint


async def test_another_rate_changes_the_fingerprint() -> None:
    assert replace(SPEECH, rate=24000).fingerprint != SPEECH.fingerprint


async def test_the_health_route_leaves_the_fingerprint_alone() -> None:
    assert replace(SPEECH, health="/v1/models").fingerprint == SPEECH.fingerprint


async def test_the_server_reached_leaves_the_fingerprint_alone() -> None:
    assert engine(httpx.MockTransport(refusing)).fingerprint == SPEECH.fingerprint
