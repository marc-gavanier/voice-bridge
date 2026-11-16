from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Frame:
    pcm: bytes
    at: float
    frame_number: int
    last: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeakerJoined:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class SpeakerLeft:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Stalled:
    waited: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Disconnected:
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Reconnected:
    pass


type Received = Frame | SpeakerJoined | SpeakerLeft | Stalled | Disconnected | Reconnected
