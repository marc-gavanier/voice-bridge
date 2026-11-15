import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import httpx
import stamina

from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES, boost, resample, resampling
from voice_bridge.libraries.audio.wav import read

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.speaking.abilities.speak.domain.ports import Pace, Pacing
    from voice_bridge.libraries.audio.pcm import Resampling, Unresampled

HEALTH_TIMEOUT: Final = 2.0
LONGEST_WAIT_FOR_READINESS: Final = 5.0
RATE_HEADER: Final = "X-Audio-Sample-Rate"
PCM_RATE: Final = 24000


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
    speed: float
    pacing: Pacing
    rate: int
    health: str


def _payload(engine: SpeechEngine, sentence: str, response_format: str) -> dict[str, str | bool]:
    return {"model": engine.model, "input": sentence, "voice": engine.voice, "response_format": response_format}


async def synthesize(engine: SpeechEngine, sentence: str) -> bytes:
    try:
        response = (
            await engine.client.post("/v1/audio/speech", json=_payload(engine, sentence, "wav"))
        ).raise_for_status()
        pcm, rate = read(response.content)
        pace = engine.pacing(rate, engine.speed)
        paced = pace.push(pcm) + pace.end()
        return boost(resample(paced, from_rate=rate, to_rate=engine.rate), engine.gain)
    except (httpx.HTTPError, wave.Error, ValueError) as error:
        raise SynthesisError(sentence) from error


@dataclass(frozen=True, slots=True, kw_only=True)
class _Shaping:
    pace: Pace
    resampling: Resampling | Unresampled
    gain: float

    def push(self, pcm: bytes) -> bytes:
        return boost(self.resampling.push(self.pace.push(pcm)), self.gain)

    def end(self) -> bytes:
        return boost(self.resampling.push(self.pace.end()) + self.resampling.end(), self.gain)


def _shaping(engine: SpeechEngine, rate: int) -> _Shaping:
    return _Shaping(pace=engine.pacing(rate, engine.speed), resampling=resampling(rate, engine.rate), gain=engine.gain)


def _whole_samples(pcm: bytes) -> tuple[bytes, bytes]:
    cut = len(pcm) - len(pcm) % SAMPLE_BYTES
    return pcm[:cut], pcm[cut:]


def _rate_of(response: httpx.Response) -> int:
    named = response.headers.get_list(RATE_HEADER)
    return int(named[0]) if named else PCM_RATE


async def _hear_some(hear: Callable[[bytes], Awaitable[None]], pcm: bytes) -> None:
    if pcm:
        await hear(pcm)


async def stream(engine: SpeechEngine, sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> None:
    payload = {**_payload(engine, sentence, "pcm"), "stream": True, "stream_format": "audio"}
    try:
        async with engine.client.stream("POST", "/v1/audio/speech", json=payload) as response:
            _ = response.raise_for_status()
            shaping = _shaping(engine, _rate_of(response))
            rest = b""
            async for chunk in response.aiter_bytes():
                whole, rest = _whole_samples(rest + chunk)
                await _hear_some(hear, shaping.push(whole))
            await _hear_some(hear, shaping.end())
    except (httpx.HTTPError, ValueError) as error:
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
