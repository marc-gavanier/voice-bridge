import json

import httpx
import numpy as np
import pytest
import stamina

from voice_bridge.features.speaking.implementation.openai_speech import (
    SpeechEngine,
    SynthesisError,
    is_ready,
    synthesize,
    wait_until_ready,
)
from voice_bridge.libraries.audio.wav import encode

pytestmark = pytest.mark.anyio

REFUSED = "connection refused"
SAMPLES = np.array([1000, -1000], dtype=np.int16).tobytes()


def engine(handler: httpx.MockTransport, gain: float = 1.0, health: str = "/health") -> SpeechEngine:
    return SpeechEngine(
        client=httpx.AsyncClient(transport=handler, base_url="http://speech"),
        model="mistralai/Voxtral-4B-TTS-2603",
        voice="fr_female",
        gain=gain,
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


async def test_a_server_error_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await synthesize(engine(httpx.MockTransport(failing)), "Bonjour.")


async def test_an_unreachable_server_is_a_synthesis_error() -> None:
    with pytest.raises(SynthesisError):
        _ = await synthesize(engine(httpx.MockTransport(refusing)), "Bonjour.")


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
