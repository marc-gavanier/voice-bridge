from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Played:
    pcm: bytes
    at: float
