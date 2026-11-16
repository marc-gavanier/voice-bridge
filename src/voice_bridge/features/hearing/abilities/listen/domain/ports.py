from typing import Protocol


class Judge(Protocol):
    def __call__(self, audio: bytes, /) -> float: ...


class VoiceDetector(Protocol):
    def __call__(self, pcm: bytes, /) -> float: ...
