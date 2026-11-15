from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import av
import av.error
import av.filter
import numpy as np

from voice_bridge.libraries.audio.pcm import SAMPLE_BYTES

if TYPE_CHECKING:
    from collections.abc import Iterator

METHOD: Final = "atempo"
NATURAL_PACE: Final = 1.0
FRAMES_PER_SECOND: Final = 50


def _frame(pcm: bytes, rate: int) -> av.AudioFrame:
    frame = av.AudioFrame.from_ndarray(np.frombuffer(pcm, dtype=np.int16).reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = rate
    return frame


def _pulled(graph: av.filter.Graph) -> Iterator[bytes]:
    while True:
        try:
            frame = graph.pull()
        except av.error.BlockingIOError, av.error.EOFError:
            return
        yield frame.to_ndarray().tobytes()


@dataclass(frozen=True, slots=True, kw_only=True)
class Unchanged:
    def push(self, pcm: bytes) -> bytes:
        return pcm

    def end(self) -> bytes:
        return b""


@dataclass(frozen=True, slots=True, kw_only=True)
class Tempo:
    graph: av.filter.Graph
    rate: int

    def push(self, pcm: bytes) -> bytes:
        step = self.rate // FRAMES_PER_SECOND * SAMPLE_BYTES
        for start in range(0, len(pcm), step):
            self.graph.push(_frame(pcm[start : start + step], self.rate))
        return b"".join(_pulled(self.graph))

    def end(self) -> bytes:
        self.graph.push(None)
        return b"".join(_pulled(self.graph))


def pace(rate: int, factor: float) -> Tempo | Unchanged:
    if factor == NATURAL_PACE:
        return Unchanged()
    graph = av.filter.Graph()
    _ = graph.link_nodes(
        graph.add_abuffer(format="s16", sample_rate=rate, layout="mono"),
        graph.add(METHOD, str(factor)),
        graph.add("abuffersink"),
    )
    graph.configure()
    return Tempo(graph=graph, rate=rate)


def stretch(pcm: bytes, rate: int, factor: float) -> bytes:
    paced = pace(rate, factor)
    return paced.push(pcm) + paced.end()
