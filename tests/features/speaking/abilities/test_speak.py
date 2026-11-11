import httpx
import pytest

from voice_bridge.features.speaking.abilities.speak import sentences_of, voice_of
from voice_bridge.features.speaking.implementations.openai_speech import SpeechEngine


def test_a_reply_becomes_sentences_written_for_the_ear() -> None:
    assert sentences_of("**Alright**, I am looking into it. See [the docs](https://x.y) right now.") == (
        "Alright, I am looking into it.",
        "See the docs right now.",
    )


def failing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, request=request)


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_skipped() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(failing), base_url="http://speech")
    engine = SpeechEngine(client=client, model="m", voice="fr_female", gain=1.0, rate=48000, health="/health")
    assert await voice_of(engine, "Hello.") is None
