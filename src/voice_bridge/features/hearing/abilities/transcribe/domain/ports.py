from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from voice_bridge.features.hearing.abilities.transcribe.domain.transcript import Transcript


class SpeechRecognizer(Protocol):
    async def recognize(self, pcm: bytes, *, rate: int, language: str) -> Transcript: ...


class Report(Protocol):
    async def __call__(self, text: str, *, noise: bool) -> None: ...
