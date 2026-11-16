from itertools import chain
from typing import TYPE_CHECKING

import av
from av.audio.resampler import AudioResampler
from av.error import InvalidDataError

from voice_bridge.libraries.audio.pcm import from_float, to_float

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from av.audio.frame import AudioFrame
    from av.container import InputContainer


def _frames(container: InputContainer) -> Iterator[AudioFrame]:
    decoded = container.decode(audio=0)
    while True:
        try:
            frame = next(decoded)
        except StopIteration:
            return
        except InvalidDataError:
            continue
        frame.pts = None
        yield frame


def _decoded(path: Path, rate: int) -> bytes:
    resampler = AudioResampler(format="s16", layout="mono", rate=rate)
    with av.open(str(path), metadata_errors="ignore") as container:
        return b"".join(
            resampled.to_ndarray().tobytes()
            for frame in chain(_frames(container), [None])
            for resampled in resampler.resample(frame)
        )


def read_audio(path: Path, *, rate: int, volume: float) -> bytes:
    return from_float(to_float(_decoded(path, rate)) * volume)
