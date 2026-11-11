from typing import TYPE_CHECKING

from faster_whisper.audio import decode_audio

from voice_bridge.libraries.audio.pcm import from_float

if TYPE_CHECKING:
    from pathlib import Path


def read_track(path: Path, *, rate: int, volume: float) -> bytes:
    return from_float(decode_audio(str(path), sampling_rate=rate) * volume)
