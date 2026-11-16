from itertools import chain
from typing import TYPE_CHECKING

import av
from av.audio.resampler import AudioResampler
from av.error import InvalidDataError

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def decode_audio(location: str, rate: int) -> Iterator[bytes]:
    resampler = AudioResampler(format="s16", layout="mono", rate=rate)
    with av.open(location, metadata_errors="ignore") as container:
        for frame in chain(_frames(container), [None]):
            for resampled in resampler.resample(frame):
                yield resampled.to_ndarray().tobytes()
