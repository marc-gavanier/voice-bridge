import httpx
import pytest

from voice_bridge.features.speaking.abilities.speak import sentences_of, voice_of
from voice_bridge.features.speaking.implementations.voxtral import Voxtral


def test_a_reply_becomes_sentences_written_for_the_ear() -> None:
    assert sentences_of("**D'accord**, je regarde ça. Voir [la doc](https://x.y) maintenant.") == (
        "D'accord, je regarde ça.",
        "Voir la doc maintenant.",
    )


def failing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, request=request)


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_skipped() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(failing), base_url="http://voxtral")
    voxtral = Voxtral(client=client, model="m", voice="fr_female", gain=1.0, rate=48000)
    assert await voice_of(voxtral, "Bonjour.") is None
