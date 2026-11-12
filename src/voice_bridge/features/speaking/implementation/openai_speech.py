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
class SpeechEngine:
    client: httpx.AsyncClient
    model: str
    voice: str
    gain: float
    rate: int
    health: str


async def synthesize(engine: SpeechEngine, sentence: str) -> bytes:
    payload = {"model": engine.model, "input": sentence, "voice": engine.voice, "response_format": "wav"}
    try:
        response = (await engine.client.post("/v1/audio/speech", json=payload)).raise_for_status()
        return boost(decode(response.content, rate=engine.rate), engine.gain)
    except (httpx.HTTPError, wave.Error, ValueError) as error:
        raise SynthesisError(sentence) from error


async def is_ready(engine: SpeechEngine) -> bool:
    if not engine.health:
        return True
    try:
        response = await engine.client.get(engine.health, timeout=HEALTH_TIMEOUT)
    except httpx.HTTPError:
        return False
    return response.is_success


async def wait_until_ready(engine: SpeechEngine) -> None:
    async for attempt in stamina.retry_context(
        on=NotReadyError, attempts=None, timeout=None, wait_max=LONGEST_WAIT_FOR_READINESS
    ):
        with attempt:
            if not await is_ready(engine):
                raise NotReadyError
