from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

from voice_bridge.libraries.audio.pcm import duration, scaled

if TYPE_CHECKING:
    from voice_bridge.features.speaking.domain.ports import Decoder

AUDIO_SUFFIXES: Final = (".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav")


class ClipRefusedError(ValueError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ClipRules:
    directory: Path
    largest: int
    longest: float
    volume: float


def _refuse(reason: str) -> NoReturn:
    raise ClipRefusedError(reason)


def _allowed(path: str, rules: ClipRules) -> Path:
    asked = Path(path)
    if not asked.is_absolute():
        _refuse(f"{path} is not an absolute path")
    found = asked.resolve()
    if not found.is_relative_to(rules.directory.resolve()):
        _refuse(f"{path} is outside {rules.directory}, where clips must be")
    if found.suffix.lower() not in AUDIO_SUFFIXES:
        _refuse(f"{path} is not an audio file: its name must end with {', '.join(AUDIO_SUFFIXES)}")
    if not found.is_file():
        _refuse(f"{path} is not a file")
    if found.stat().st_size > rules.largest:
        _refuse(f"{path} weighs over {rules.largest} bytes")
    return found


def read_clip(path: str, *, rules: ClipRules, rate: int, decode: Decoder) -> bytes:
    found = _allowed(path, rules)
    try:
        pcm = scaled(b"".join(decode(str(found), rate)), rules.volume)
    except ValueError as error:
        message = f"{path} holds no audio FFmpeg can read"
        raise ClipRefusedError(message) from error
    if not pcm:
        _refuse(f"{path} holds no sound")
    lasting = duration(pcm, rate)
    if lasting > rules.longest:
        _refuse(f"{path} lasts {lasting:.0f} s, over the {rules.longest:.0f} s allowed")
    return pcm
