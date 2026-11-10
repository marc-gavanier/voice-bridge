import wave
from dataclasses import dataclass
from typing import Final

import httpx
import stamina

from voice_bridge.libraries.audio.pcm import boost
from voice_bridge.libraries.audio.wav import decode

HEALTH_TIMEOUT: Final = 2.0
LONGEST_WAIT_FOR_READINESS: Final = 5.0


class SynthesisError(Exception):
    pass


class NotReadyError(Exception):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Voxtral:
    client: httpx.AsyncClient
    model: str
    voice: str
    gain: float
    rate: int


async def synthesize(voxtral: Voxtral, sentence: str) -> bytes:
    payload = {"model": voxtral.model, "input": sentence, "voice": voxtral.voice, "response_format": "wav"}
    try:
        response = (await voxtral.client.post("/v1/audio/speech", json=payload)).raise_for_status()
        return boost(decode(response.content, rate=voxtral.rate), voxtral.gain)
    except (httpx.HTTPError, wave.Error, ValueError) as error:
        raise SynthesisError(sentence) from error


async def is_ready(voxtral: Voxtral) -> bool:
    try:
        response = await voxtral.client.get("/health", timeout=HEALTH_TIMEOUT)
    except httpx.HTTPError:
        return False
    return response.is_success


async def wait_until_ready(voxtral: Voxtral) -> None:
    async for attempt in stamina.retry_context(
        on=NotReadyError, attempts=None, timeout=None, wait_max=LONGEST_WAIT_FOR_READINESS
    ):
        with attempt:
            if not await is_ready(voxtral):
                raise NotReadyError
