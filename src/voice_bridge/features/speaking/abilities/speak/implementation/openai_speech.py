import math
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import anyio
import httpx

from voice_bridge.features.speaking.abilities.speak.domain.ports import SynthesisError
from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES, boost, resample, resampling
from voice_bridge.libraries.audio.wav import read

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from voice_bridge.features.speaking.abilities.speak.domain.ports import Pace, Pacing
    from voice_bridge.libraries.audio.pcm import Resampling, Unresampled

HEALTH_TIMEOUT: Final = 2.0
RATE_HEADER: Final = "X-Audio-Sample-Rate"
PCM_RATE: Final = 24000
SPEECH_ROUTE: Final = "/v1/audio/speech"
ADAPTER: Final = "openai-compatible"


@dataclass(frozen=True, slots=True, kw_only=True)
class _Shaping:
    pace: Pace
    resampling: Resampling | Unresampled
    gain: float

    def push(self, pcm: bytes) -> bytes:
        return boost(self.resampling.push(self.pace.push(pcm)), self.gain)

    def end(self) -> bytes:
        return boost(self.resampling.push(self.pace.end()) + self.resampling.end(), self.gain)


def _whole_samples(pcm: bytes) -> tuple[bytes, bytes]:
    cut = len(pcm) - len(pcm) % SAMPLE_BYTES
    return pcm[:cut], pcm[cut:]


def _rate_of(response: httpx.Response) -> int:
    named = response.headers.get_list(RATE_HEADER)
    return int(named[0]) if named else PCM_RATE


def client(url: str, *, timeout: float, connect_timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=url, timeout=httpx.Timeout(timeout, connect=connect_timeout))


async def _hear_some(hear: Callable[[bytes], Awaitable[None]], pcm: bytes) -> None:
    if pcm:
        await hear(pcm)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAICompatibleSpeech:
    client: httpx.AsyncClient
    model: str
    voice: str
    gain: float
    speed: float
    pacing: Pacing
    rate: int
    health: str
    first_audio_timeout: float

    @property
    def fingerprint(self) -> str:
        return f"{ADAPTER} {self.model} {self.voice} {self.gain} {self.speed} {self.rate}"

    def _payload(self, sentence: str, response_format: str) -> dict[str, str | bool]:
        return {"model": self.model, "input": sentence, "voice": self.voice, "response_format": response_format}

    def _shaping(self, rate: int) -> _Shaping:
        return _Shaping(pace=self.pacing(rate, self.speed), resampling=resampling(rate, self.rate), gain=self.gain)

    async def whole(self, sentence: str) -> bytes:
        try:
            response = (await self.client.post(SPEECH_ROUTE, json=self._payload(sentence, "wav"))).raise_for_status()
            pcm, rate = read(response.content)
            pace = self.pacing(rate, self.speed)
            paced = pace.push(pcm) + pace.end()
            return boost(resample(paced, from_rate=rate, to_rate=self.rate), self.gain)
        except (httpx.HTTPError, wave.Error, ValueError) as error:
            raise SynthesisError(sentence) from error

    async def stream(self, sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> None:
        payload = {**self._payload(sentence, "pcm"), "stream": True, "stream_format": "audio"}
        try:
            with anyio.fail_after(self.first_audio_timeout) as first_audio:
                async with self.client.stream("POST", SPEECH_ROUTE, json=payload) as response:
                    _ = response.raise_for_status()
                    shaping = self._shaping(_rate_of(response))
                    rest = b""
                    async for chunk in response.aiter_bytes():
                        first_audio.deadline = math.inf
                        whole, rest = _whole_samples(rest + chunk)
                        await _hear_some(hear, shaping.push(whole))
                    await _hear_some(hear, shaping.end())
        except (httpx.HTTPError, ValueError, TimeoutError) as error:
            raise SynthesisError(sentence) from error

    async def ready(self) -> bool:
        if not self.health:
            return True
        try:
            response = await self.client.get(self.health, timeout=HEALTH_TIMEOUT)
        except httpx.HTTPError:
            return False
        return response.is_success
