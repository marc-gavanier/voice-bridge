import httpx
import pytest

from voice_bridge.features.speaking.abilities.speak.domain.ports import Pace
from voice_bridge.features.speaking.abilities.speak.implementation.openai_speech import SpeechEngine
from voice_bridge.features.speaking.abilities.speak.implementation.speak import sentences_of, voice_of, voice_streamed


def test_a_reply_becomes_sentences_written_for_the_ear() -> None:
    assert sentences_of("**Alright**, I am looking into it. See [the docs](https://x.y) right now.") == (
        "Alright, I am looking into it.",
        "See the docs right now.",
    )


class KeptPace:
    def push(self, pcm: bytes) -> bytes:
        return pcm

    def end(self) -> bytes:
        return b""


def kept(_rate: int, _factor: float) -> Pace:
    return KeptPace()


def failing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, request=request)


def answering(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"X-Audio-Sample-Rate": "48000"}, content=SAMPLES, request=request)


SAMPLES = b"\x10\x00\xf0\xff"


def engine_answering(handler: httpx.MockTransport) -> SpeechEngine:
    return SpeechEngine(
        client=httpx.AsyncClient(transport=handler, base_url="http://speech"),
        model="m",
        voice="fr_female",
        gain=1.0,
        speed=1.0,
        pacing=kept,
        rate=48000,
        health="/health",
    )


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_skipped() -> None:
    assert await voice_of(engine_answering(httpx.MockTransport(failing)), "Hello.") is None


async def ignored(_pcm: bytes) -> None:
    pass


@pytest.mark.anyio
async def test_a_streamed_sentence_without_voice_tells_its_voice_failed() -> None:
    assert not await voice_streamed(engine_answering(httpx.MockTransport(failing)), "Hello.", ignored)


@pytest.mark.anyio
async def test_a_streamed_sentence_without_voice_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    _ = await voice_streamed(engine_answering(httpx.MockTransport(failing)), "Hello.", ignored)
    assert "no voice for 'Hello.'" in caplog.text


@pytest.mark.anyio
async def test_a_streamed_sentence_tells_its_voice_came_whole() -> None:
    assert await voice_streamed(engine_answering(httpx.MockTransport(answering)), "Hello.", ignored)
