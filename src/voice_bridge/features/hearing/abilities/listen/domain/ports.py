from typing import Protocol


class Judge(Protocol):
    def __call__(self, audio: bytes, /) -> float: ...


class VoiceDetector(Protocol):
    def __call__(self, pcm: bytes, /) -> float: ...


class Sound(Protocol):
    @property
    def pcm(self) -> bytes: ...
    @property
    def at(self) -> float: ...
