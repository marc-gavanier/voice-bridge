from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from voice_bridge.libraries.audio.pcm import duration, scaled

if TYPE_CHECKING:
    from voice_bridge.features.speaking.domain.ports import AudioSource


class ClipRefusedError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ClipRules:
    longest: float
    volume: float


def _refuse(reason: str) -> NoReturn:
    raise ClipRefusedError(reason)


def read_clip(path: str, *, source: AudioSource, rules: ClipRules, rate: int) -> bytes:
    audio = source.find(path)
    try:
        pcm = scaled(b"".join(audio.frames), rules.volume)
    except ValueError as error:
        message = f"{path} holds no audio FFmpeg can read"
        raise ClipRefusedError(message) from error
    if not pcm:
        _refuse(f"{path} holds no sound")
    lasting = duration(pcm, rate)
    if lasting > rules.longest:
        _refuse(f"{path} lasts {lasting:.0f} s, over the {rules.longest:.0f} s allowed")
    return pcm
